# Testing

### Prerequisites
- DevContainer, or a system that replicates the configuration in .devcontainer/devcontainer.json

## How to run
- Open a terminal.
- Run `just api` to initialise the k3s.
- Run `just test` to run the tests.

## Implementation guideline of tests
- Each test method should ideally make one RSSMonk API call.
- Group calls to the same endpoint is permitted with the following rules:
    1. Ensure that the calls do not compromise the existing integrity of the data.
    2. Any data modification is the final API interaction to RSSMonk in the test method, followed by assertions to verify.