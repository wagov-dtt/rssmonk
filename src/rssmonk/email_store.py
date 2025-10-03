# TODO - Set up a store in Postgres for the email templates.
# TODO - This is likely not required, open up api endpoint for an admin to send data to

from rssmonk.utils import make_url_hash


class EmailTemplate:
    name: str
    subject: str
    body: str

class EmailTemplateStore:
    def store_subscribe_template(self, feed_url: str, template: EmailTemplate) -> bool:
        return True


    def store_unsubscribe_template(self, feed_url: str, template: EmailTemplate) -> bool:
        return True


    def get_subscribe_email(self, feed_url: str) -> EmailTemplate:
        returnVal: EmailTemplate = EmailTemplate()

        returnVal.name = f"{make_url_hash(feed_url)}-subscribe"
        returnVal.subject = "{{ .Tx.Data.subject }}"
        returnVal.body= """
<html><body>
Hi,<p>
Thanks for subscribing to media statement updates from the WA Government.<br>
You’ve chosen to receive updates for:<p>
{{- range $item := .Tx.Data.filter }}
- {{ $item }}
{{- end }}  
To start getting updates, you need to verify your email address.<br>
Please click the link below to verify your email address:<p>
<a href="{{ .Tx.Data.confirmation_link }}" target="_blank" rel="noopener noreferrer">{{ .Tx.Data.confirmation_link }}</a><p>
For your security, this link will expire in 24 hours.<p>
If it has expired, you can return to the manage subscription page <a href="{{ .Tx.Data.subscription_link }}" target="_blank" rel="noopener noreferrer">here</a> and start again.<p>
If you did not make this request, please ignore this email.<p>
Thank you.<br>
WA Government Media Statement Team.
</body></html>
"""
        return returnVal


    def get_unsubscribe_email_tempate(self, feed_url: str) -> EmailTemplate:
        returnVal: EmailTemplate = EmailTemplate()

        returnVal.name = f"{make_url_hash(feed_url)}-subscribe"
        returnVal.subject = "{{ .Tx.Data.subject }}"
        returnVal.body= """
<html><body>
You’ve successfully unsubscribed.<p>
You will no longer receive media statement updates.<p>
If you didn’t mean to unsubscribe, you can resubscribe anytime by visiting the <a href="{{subscription_link}}" target="_blank" rel="noopener noreferrer">manage your subscription</a> page.<p>
Thanks,<br>
WA Government Media Statement Team.
</body></html>
"""
        return returnVal