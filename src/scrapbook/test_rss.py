import uuid
import warnings
warnings.warn("This module should not be imported for use. It is solely for a test", DeprecationWarning)

# This script is to test for access
import requests

_URL = "http://localhost:9000"


if __name__ == "__main__":
    """
    RSS feed test
    """
    session = requests.Session()
    response = session.get("https://www.wa.gov.au/rss/media-statements")
    # 403 due to Cloudfront
    print(response.text)

    for i in range(5):
        adata = str(uuid.uuid4())[0:(32-3)] + f"{i}".zfill(3)
        print(adata)