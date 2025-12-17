"""Subscription management endpoints - subscribe, confirm, unsubscribe."""

import traceback
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from rssmonk.core import RSSMonk, Settings
from rssmonk.logging_config import get_logger
from rssmonk.models import (
    SubscribeAdminRequest,
    SubscribeConfirmRequest,
    SubscribeRequest,
    SubscriptionPreferencesRequest,
    SubscriptionPreferencesResponse,
    SubscriptionResponse,
    UnsubscribeAdminRequest,
    UnsubscribeRequest,
    EmailPhaseType,
)
from rssmonk.types import NO_REPLY_EMAIL, ActionsURLSuffix
from rssmonk.utils import (
    extract_feed_hash,
    get_feed_hash_from_username,
    make_filter_url,
    make_url_hash,
    numberfy_subbed_lists,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/feeds", tags=["feeds"])
security = HTTPBasic()


@router.get(
    "/subscribe-preferences",
    response_model=SubscriptionPreferencesResponse,
    summary="Get Feed preferences",
    description="Request the preferences of an email address' RSS feed subscription. Authentication required"
)
async def get_subscription_preferences(
    request: SubscriptionPreferencesRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> SubscriptionPreferencesResponse:
    """Get feed subscription user's preferences."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            rss_monk.validate_feed_visibility(make_url_hash(str(request.feed_url)))
            attribs = rss_monk.get_subscriber_feed_filter(request.email)
            if attribs is not None:
                feed_hash = get_feed_hash_from_username(credentials.username)
                if request.feed_url is None:
                    feed_hash = make_url_hash(str(request.feed_url))
                return_filter = {feed_hash: attribs.get(feed_hash, {}).get("filter", {}).get(feed_hash, {})}
                return SubscriptionPreferencesResponse(filter=return_filter)
            return SubscriptionPreferencesResponse(filter={})
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Subscription fetch failed: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription retrieval failed")


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    summary="Subscribe to a Feed",
    description="Subscribe an email address to an RSS feed. Authentication required"
)
async def subscribe(
    request: SubscribeRequest | SubscribeAdminRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> SubscriptionResponse:
    """Subscribe email to a feed."""
    settings = Settings()
    rss_monk = RSSMonk(local_creds=credentials)
    with rss_monk:
        bypass_confirmation = False
        feed_hash = None
        is_valid_admin = settings.validate_admin_auth(credentials.username, credentials.password)
        if isinstance(request, SubscribeAdminRequest):
            if not is_valid_admin:
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
            bypass_confirmation = request.bypass_confirmation is not None and request.bypass_confirmation
            feed_hash = make_url_hash(str(request.feed_url))
        else:
            if is_valid_admin:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="")
            feed_hash = get_feed_hash_from_username(credentials.username)
        rss_monk.validate_feed_visibility(feed_hash)

        try:
            rss_monk.subscribe(request.email, feed_hash)
            subscriber_uuid = rss_monk.get_subscriber_uuid(request.email)
            subscriber_uuid = subscriber_uuid.replace("-", "")

            if len(request.filter.keys()) > 1:
                raise HTTPException(
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    detail="Only one frequency is permitted per subscription request"
                )
            frequency = list(request.filter.keys())[0]

            pending_uuid = rss_monk.update_subscriber_filter(
                request.email,
                request.filter,
                feed_hash,
                bypass_confirmation=bypass_confirmation
            )
            if not bypass_confirmation:
                feed_data = rss_monk.get_feed_by_hash(feed_hash)
                base_url = feed_data.email_base_url

                template = rss_monk.get_template_metadata(feed_hash, EmailPhaseType.SUBSCRIBE)
                if template is None:
                    logger.error("No subscribe template found for %s", feed_hash)
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_REQUEST,
                        detail=f"Pending subscription added, but template dependency missing for {EmailPhaseType.SUBSCRIBE.value}"
                    )

                subscribe_link = f"{base_url}/{ActionsURLSuffix.SUBSCRIBE.value}?{make_filter_url(request.filter[frequency])}"
                transaction = {
                    "subject": None,
                    "subscription_link": subscribe_link,
                    "frequency": frequency,
                    "filter": request.display_text[frequency] if request.display_text and (frequency in request.display_text) else {},
                    "confirmation_link": f"{base_url}/{ActionsURLSuffix.CONFIRM.value}?id={subscriber_uuid}&guid={pending_uuid}"
                }

                rss_monk.getClient().send_transactional(NO_REPLY_EMAIL, template.id, "html", [request.email], transaction)

            return SubscriptionResponse(message="Subscription successful")
        except ValueError as e:
            logger.error("Subscribe: %s", e)
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
        except HTTPException as e:
            logger.error("Subscribe: %s", e)
            raise
        except Exception as e:
            logger.error("Subscribe: %s", e)
            traceback.print_exc()
            raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription failed")


@router.post(
    "/subscribe-confirm",
    status_code=HTTPStatus.OK,
    summary="Confirm subscription to a Feed",
    description="Confirm the filtered subscription of an email address to an RSS feed. Authentication required"
)
async def confirm_subscription(
    request: SubscribeConfirmRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Confirm feed subscription."""
    settings = Settings()
    rss_monk = RSSMonk(local_creds=credentials)
    try:
        with rss_monk:
            if settings.validate_admin_auth(credentials.username, credentials.password):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="Administrators must use the bypass when subscribing"
                )

            rss_monk.validate_feed_visibility(get_feed_hash_from_username(credentials.username))
            feed_hash = extract_feed_hash(credentials.username)

            subscriber_uuid = request.subscriber_id
            sub_list = rss_monk.getAdminClient().get_subscribers(query=f"subscribers.uuid='{subscriber_uuid}'")

            req_uuid = request.guid
            subs = sub_list[0] if (isinstance(sub_list, list) and len(sub_list) > 0) else None
            if not subs:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Invalid details")

            if feed_hash not in subs["attribs"]:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Link has expired")

            feed_attribs = subs["attribs"][feed_hash]
            if req_uuid not in feed_attribs:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Link has expired")

            if feed_attribs[req_uuid]['expires'] < datetime.now(timezone.utc).timestamp():
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Link has expired")

            feed_attribs["filter"] = feed_attribs[req_uuid]["filter"]
            feed_attribs["token"] = uuid.uuid4().hex
            feed_attribs["subscribe_query"] = f"/{ActionsURLSuffix.SUBSCRIBE.value}?{make_filter_url(feed_attribs['filter'])}"
            feed_attribs["unsubscribe_query"] = f"/{ActionsURLSuffix.UNSUBSCRIBE.value}?id={subscriber_uuid}&token={feed_attribs['token']}"

            del subs["attribs"][feed_hash][req_uuid]
            subs["lists"] = numberfy_subbed_lists(subs["lists"])
            rss_monk.getClient().update_subscriber(subs["id"], subs)

    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to confirm subscription: %s", e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription confirmation failed")


@router.post(
    "/unsubscribe",
    status_code=HTTPStatus.OK,
    summary="Unsubscribe from a Feed",
    description="Removes the email address from a RSS feed. Authentication required"
)
async def unsubscribe(
    request: UnsubscribeRequest | UnsubscribeAdminRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Unsubscribe from a feed."""
    settings = Settings()
    rss_monk = RSSMonk(local_creds=credentials)
    try:
        with rss_monk:
            remove_subscriber = False
            feed_hash = None
            token = None
            bypass_confirmation = False
            subscriber_query = None
            is_valid_admin = settings.validate_admin_auth(credentials.username, credentials.password)

            if isinstance(request, UnsubscribeAdminRequest):
                if not is_valid_admin:
                    raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
                bypass_confirmation = request.bypass_confirmation is not None and request.bypass_confirmation
                feed_hash = make_url_hash(str(request.feed_url))
                subscriber_query = f"subscribers.email='{request.email}'"
            else:
                if is_valid_admin:
                    raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="")
                feed_hash = get_feed_hash_from_username(credentials.username)
                subscriber_query = f"subscribers.uuid='{request.subscriber_id}'"
                token = request.token

            rss_monk.validate_feed_visibility(feed_hash)

            sub_list = rss_monk.getAdminClient().get_subscribers(query=subscriber_query)
            subscriber_details = sub_list[0] if (isinstance(sub_list, list) and len(sub_list) > 0) else None
            if not subscriber_details:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Invalid subscriber details")

            feed_list = rss_monk.getClient().find_list_by_tag(f"url:{feed_hash}")
            if feed_list is None:
                if feed_hash in credentials.username:
                    logger.warning("Non-existent feed (hash: %s) access with user account %s. Possible misconfiguration",
                                   feed_hash, credentials.username)
                return
            feed_data = rss_monk._parse_feed_from_list(feed_list)

            subs_lists = numberfy_subbed_lists(subscriber_details["lists"])
            if feed_data.id in subs_lists:
                subs_lists.remove(feed_data.id)
            subscriber_details["lists"] = subs_lists

            previous_filter = {}
            if feed_hash in subscriber_details["attribs"]:
                previous_filter = subscriber_details["attribs"][feed_hash]
                if not is_valid_admin and token != previous_filter["token"]:
                    raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Incorrect token")
                del subscriber_details["attribs"][feed_hash]

            if len(subs_lists) == 0:
                remove_subscriber = True

            rss_monk.getClient().update_subscriber(subscriber_details["id"], subscriber_details)

            if not bypass_confirmation:
                template = rss_monk.get_template_metadata(feed_hash, EmailPhaseType.UNSUBSCRIBE)
                if template is None:
                    logger.error("No unsubscribe template found for feed %s. Skipping", feed_hash)
                    return

                try:
                    subscribe_link = f"{feed_data.email_base_url}/{ActionsURLSuffix.SUBSCRIBE.value}?{make_filter_url(previous_filter)}"
                    rss_monk.getClient().send_transactional(
                        NO_REPLY_EMAIL,
                        template.id,
                        "html",
                        [subscriber_details["email"]],
                        {"subscription_link": subscribe_link}
                    )
                except Exception as e:
                    logger.error("Failed to send unsubscribe email: %s. Subscriber with email %s will be changed",
                                 e, subscriber_details["email"])
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail="Requested email could not be sent"
                    ) from e

            if remove_subscriber:
                rss_monk.getAdminClient().delete_subscriber(subscriber_details["id"])

    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    except HTTPException as e:
        if e.status_code == HTTPStatus.NOT_FOUND:
            raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="Invalid details provided.")
        raise
    except Exception as e:
        logger.error("Failed to unsubscribe: %s", e)
        traceback.print_exception(e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unsubscribe failed") from e
