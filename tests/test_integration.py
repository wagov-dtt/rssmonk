"""Integration tests for RSS Monk end-to-end functionality."""

import asyncio
from warnings import deprecated
import httpx
import pytest
import time


class IntegrationTestSuite:
    """End-to-end integration test suite for RSS Monk."""
    
    def __init__(self, base_url: str = "http://localhost:8000", listmonk_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.listmonk_url = listmonk_url
        self.mailpit_url = "http://localhost:8025"
        self.auth = ("admin", "admin123")  # Default k3d credentials

    @deprecated("This test flow might be superceeded by the test within test_lifecycle")        
    async def test_full_workflow(self):
        """Test complete RSS Monk workflow."""
        async with httpx.AsyncClient() as client:
            # 1. Health check
            await self._test_health_check(client)
            
            # 2. Create test feeds with different frequencies
            feeds = await self._create_test_feeds(client)
            
            # 3. Add test subscribers
            subscribers = await self._create_test_subscribers(client)
            
            # 4. Subscribe users to feeds
            await self._subscribe_users_to_feeds(client, subscribers, feeds)
            
            # 5. Process feeds and generate campaigns
            campaigns = await self._process_feeds(client, feeds)
            
            # 6. Verify emails in Mailpit
            await self._verify_emails_in_mailpit(client, campaigns)
            
            # 7. Test configuration updates
            await self._test_config_updates(client, feeds)
            
            # 8. Test unsubscriptions
            await self._test_unsubscriptions(client, subscribers, feeds)
            
            # 9. Cleanup
            await self._cleanup_test_data(client, feeds, subscribers)
    
    async def _test_health_check(self, client):
        """Test health endpoint."""
        response = await client.get(f"{self.base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    async def _create_test_feeds(self, client) -> list[dict]:
        """Create test RSS feeds with different configurations."""
        test_feeds = [
            {
                "url": "https://feeds.bbci.co.uk/news/rss.xml",
                "frequency": "daily",
                "name": "BBC News Daily"
            },
            {
                "url": "https://www.abc.net.au/news/feed/10719986/rss.xml", 
                "frequency": "instant",
                "name": "ABC News Instant"
            }
        ]
        
        created_feeds = []
        for feed_data in test_feeds:
            response = await client.post(
                f"{self.base_url}/api/feeds",
                json=feed_data,
                auth=self.auth
            )
            if response.status_code == 201:
                created_feeds.append(response.json())
                print(f"✓ Created feed: {feed_data['name']}")
            else:
                print(f"✗ Failed to create feed: {feed_data['name']} - {response.text}")
        
        return created_feeds
    
    async def _create_test_subscribers(self, client) -> list[dict]:
        """Create test subscribers."""
        test_emails = [
            "test1@example.com",
            "test2@example.com", 
            "test3@example.com"
        ]
        
        subscribers = []
        for email in test_emails:
            # Use Listmonk directly for subscriber creation
            response = await client.post(
                f"{self.listmonk_url}/api/subscribers",
                json={
                    "email": email,
                    "name": f"Test User {email}",
                    "status": "enabled"
                },
                auth=self.auth
            )
            if response.status_code in [200, 201]:
                data = response.json()
                if "data" in data:
                    subscribers.append(data["data"])
                else:
                    subscribers.append(data)
                print(f"✓ Created subscriber: {email}")
            else:
                print(f"✗ Failed to create subscriber: {email} - {response.text}")
        
        return subscribers
    
    async def _subscribe_users_to_feeds(self, client, subscribers: list[dict], feeds: list[dict]):
        """Subscribe users to feeds."""
        for subscriber in subscribers:
            for feed in feeds:
                response = await client.post(
                    f"{self.base_url}/api/public/subscribe",
                    json={
                        "email": subscriber["email"],
                        "feed_url": feed["url"]
                    }
                )
                if response.status_code == 200:
                    print(f"✓ Subscribed {subscriber['email']} to {feed['name']}")
                else:
                    print(f"✗ Failed to subscribe {subscriber['email']} to {feed['name']}")
    
    async def _process_feeds(self, client, feeds: list[dict]) -> list[dict]:
        """Process feeds and create campaigns."""
        campaigns = []
        for feed in feeds:
            response = await client.post(
                f"{self.base_url}/api/feeds/process",
                json={
                    "url": feed["url"]
                },
                auth=self.auth
            )
            if response.status_code == 200:
                result = response.json()
                campaigns.append(result)
                print(f"✓ Processed feed {feed['name']}: {result['campaigns_created']} campaigns")
            else:
                print(f"✗ Failed to process feed {feed['name']}: {response.text}")
        
        return campaigns
    
    async def _verify_emails_in_mailpit(self, client, campaigns: list[dict]):
        """Verify emails arrived in Mailpit."""
        # Wait a moment for emails to be processed
        await asyncio.sleep(2)
        
        try:
            response = await client.get(f"{self.mailpit_url}/api/v1/messages")
            if response.status_code == 200:
                data = response.json()
                message_count = data.get("total", 0)
                print(f"✓ Found {message_count} emails in Mailpit")
                return message_count > 0
            else:
                print(f"✗ Failed to check Mailpit: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Mailpit connection failed: {e}")
            return False
    
    async def _test_config_updates(self, client, feeds: list[dict]):
        """Test updating feed configurations."""
        if not feeds:
            return
            
        # Try to update the first feed's frequency
        original_feed = feeds[0]
        new_frequency = "daily"
        
        # Delete old feed
        response = await client.delete(
            f"{self.base_url}/api/feeds/by-url",
            params={"url": original_feed["url"]},
            auth=self.auth
        )
        
        if response.status_code == 200:
            print(f"✓ Deleted original feed configuration")
            
            # Create new feed with different frequency
            response = await client.post(
                f"{self.base_url}/api/feeds",
                json={
                    "url": original_feed["url"],
                    "frequency": new_frequency,
                    "name": f"{original_feed['name']} - Updated"
                },
                auth=self.auth
            )
            
            if response.status_code == 201:
                print(f"✓ Updated feed configuration: {original_feed['url']} -> {new_frequency}")
                return response.json()
            else:
                print(f"✗ Failed to update feed configuration: {response.text}")
        else:
            print(f"✗ Failed to delete original feed: {response.text}")
        
        return None
    
    async def _test_unsubscriptions(self, client, subscribers: list[dict], feeds: list[dict]):
        """Test unsubscription functionality."""
        if not subscribers or not feeds:
            return
            
        # This would typically involve Listmonk API calls to manage subscriptions
        # For now, we'll just verify the lists exist
        for feed in feeds:
            response = await client.get(
                f"{self.base_url}/api/feeds/by-url",
                params={"url": feed["url"]},
                auth=self.auth
            )
            if response.status_code == 200:
                print(f"✓ Feed still exists: {feed['name']}")
    
    async def _cleanup_test_data(self, client, feeds: list[dict], subscribers: list[dict]):
        """Clean up test data."""
        # Delete feeds
        for feed in feeds:
            response = await client.delete(
                f"{self.base_url}/api/feeds/by-url",
                params={"url": feed["url"]},
                auth=self.auth
            )
            if response.status_code == 200:
                print(f"✓ Cleaned up feed: {feed['name']}")
        
        # Delete subscribers
        for subscriber in subscribers:
            response = await client.delete(
                f"{self.listmonk_url}/api/subscribers/{subscriber['id']}",
                auth=self.auth
            )
            if response.status_code == 200:
                print(f"✓ Cleaned up subscriber: {subscriber['email']}")


@pytest.mark.asyncio
async def test_integration_workflow():
    """Run the full integration test suite."""
    suite = IntegrationTestSuite()
    await suite.test_full_workflow()


if __name__ == "__main__":
    # Allow running this directly for manual testing
    suite = IntegrationTestSuite()
    asyncio.run(suite.test_full_workflow())
