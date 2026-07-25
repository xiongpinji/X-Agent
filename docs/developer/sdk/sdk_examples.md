# SDK Examples

This directory contains code examples for integrating with X-Agent Partner API using different SDKs.

## Table of Contents

1. [Python Examples](#python-examples)
2. [JavaScript/TypeScript Examples](#javascripttypescript-examples)
3. [Go Examples](#go-examples)
4. [Java Examples](#java-examples)

---

## Python Examples

### Installation

```bash
pip install xagent-partner-sdk
```

### Basic Usage

```python
from xagent_partner import PartnerClient

# Initialize client
client = PartnerClient(api_key="xag_partner_xxx")

# Register partner
partner = client.register_partner(
    company_name="Acme Corp",
    contact_email="contact@acme.com",
    contact_name="John Doe",
    integration_type="standard"
)
print(f"Partner registered: {partner['partner_id']}")

# Create API key
api_key = client.create_api_key(
    partner_id=partner["partner_id"],
    name="Production Key",
    expires_in_days=365,
    rate_limit_rpm=1000
)
print(f"API key created: {api_key['key_prefix']}")
print(f"Full key (save securely): {api_key['key']}")

# Get usage
usage = client.get_usage(partner_id=partner["partner_id"])
print(f"Usage: {usage['total_requests']} requests")

client.close()
```

### Webhook Integration

```python
from flask import Flask, request
from xagent_partner import PartnerClient
import json

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

client = PartnerClient(api_key="xag_partner_xxx")

# Register webhook
webhook = client.register_webhook(
    partner_id="partner_id",
    event_type="partner.api_key.created",
    url="https://yourapp.com/webhooks/xagent",
    retry_policy={
        "max_retries": 5,
        "backoff_multiplier": 2,
        "initial_delay_seconds": 1
    }
)

@app.route('/webhooks/xagent', methods=['POST'])
def handle_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    body = request.get_data()
    
    if not PartnerClient.verify_webhook_signature(body, signature, WEBHOOK_SECRET):
        return {'error': 'Invalid signature'}, 401
    
    # Process event
    event = json.loads(body)
    print(f"Received event: {event['event_type']}")
    
    if event['event_type'] == 'partner.api_key.created':
        print(f"New API key: {event['data']['key_prefix']}")
    
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    app.run(ssl_context='adhoc')
```

### Error Handling

```python
from xagent_partner import (
    PartnerClient,
    PartnerAPIError,
    PartnerAuthError,
    PartnerRateLimitError
)

client = PartnerClient(api_key="xag_partner_xxx")

try:
    partner = client.get_partner("invalid_id")
except PartnerAuthError as e:
    print(f"Authentication failed: {e}")
except PartnerRateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except PartnerAPIError as e:
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response}")
```

---

## JavaScript/TypeScript Examples

### Installation

```bash
npm install xagent-partner-sdk
```

### Basic Usage

```typescript
import { PartnerClient } from 'xagent-partner-sdk';

async function main() {
  const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });

  try {
    // Register partner
    const partner = await client.registerPartner({
      company_name: 'Acme Corp',
      contact_email: 'contact@acme.com',
      contact_name: 'John Doe',
      integration_type: 'standard'
    });
    console.log(`Partner registered: ${partner.partner_id}`);

    // Create API key
    const apiKey = await client.createAPIKey(partner.partner_id, {
      name: 'Production Key',
      expires_in_days: 365,
      rate_limit_rpm: 1000
    });
    console.log(`API key created: ${apiKey.key_prefix}`);
    console.log(`Full key (save securely): ${apiKey.key}`);

    // Get usage
    const usage = await client.getUsage(partner.partner_id);
    console.log(`Usage: ${usage.total_requests} requests`);
  } catch (error) {
    console.error('Error:', error);
  }
}

main();
```

### Webhook Integration

```typescript
import express from 'express';
import { PartnerClient } from 'xagent-partner-sdk';

const app = express();
const WEBHOOK_SECRET = 'your_webhook_secret';
const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });

// Register webhook
await client.registerWebhook('partner_id', {
  event_type: 'partner.api_key.created',
  url: 'https://yourapp.com/webhooks/xagent',
  retry_policy: {
    max_retries: 5,
    backoff_multiplier: 2,
    initial_delay_seconds: 1
  }
});

app.post('/webhooks/xagent', express.json(), (req, res) => {
  // Verify signature
  const signature = req.headers['x-webhook-signature'] as string;
  const body = JSON.stringify(req.body);

  if (!PartnerClient.verifyWebhookSignature(body, signature, WEBHOOK_SECRET)) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Process event
  const event = req.body;
  console.log(`Received event: ${event.event_type}`);

  if (event.event_type === 'partner.api_key.created') {
    console.log(`New API key: ${event.data.key_prefix}`);
  }

  res.json({ status: 'ok' });
});

app.listen(3000, () => {
  console.log('Webhook server running on port 3000');
});
```

### Error Handling

```typescript
import {
  PartnerClient,
  PartnerAPIError,
  PartnerAuthError,
  PartnerRateLimitError
} from 'xagent-partner-sdk';

const client = new PartnerClient({ apiKey: 'xag_partner_xxx' });

try {
  const partner = await client.getPartner('invalid_id');
} catch (error) {
  if (error instanceof PartnerAuthError) {
    console.error(`Authentication failed: ${error.message}`);
  } else if (error instanceof PartnerRateLimitError) {
    console.error(`Rate limit exceeded: ${error.message}`);
  } else if (error instanceof PartnerAPIError) {
    console.error(`API error: ${error.message}`);
    console.error(`Status code: ${error.statusCode}`);
    console.error(`Response: ${error.response}`);
  }
}
```

---

## Go Examples

### Installation

```bash
go get github.com/xagent/partner-sdk-go
```

### Basic Usage

```go
package main

import (
	"fmt"
	"log"
	"time"

	"github.com/xagent/partner-sdk-go"
)

func main() {
	// Initialize client
	client := xagent.NewPartnerClient(xagent.PartnerClientConfig{
		APIKey:    "xag_partner_xxx",
		BaseURL:   "https://api.x-agent.io",
		Timeout:   30 * time.Second,
		MaxRetries: 3,
	})

	// Register partner
	partner, err := client.RegisterPartner(xagent.PartnerRegistrationRequest{
		CompanyName:     "Acme Corp",
		ContactEmail:    "contact@acme.com",
		ContactName:     "John Doe",
		IntegrationType: "standard",
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Partner registered: %s\n", partner.PartnerID)

	// Create API key
	apiKey, err := client.CreateAPIKey(partner.PartnerID, xagent.APIKeyRequest{
		Name:          "Production Key",
		ExpiresInDays: 365,
		RateLimitRPM:  1000,
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("API key created: %s\n", apiKey.KeyPrefix)
	fmt.Printf("Full key (save securely): %s\n", apiKey.Key)

	// Get usage
	usage, err := client.GetUsage(partner.PartnerID, "current_month", "", "")
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Usage: %d requests\n", usage.TotalRequests)
}
```

### Webhook Integration

```go
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"

	"github.com/xagent/partner-sdk-go"
)

const WEBHOOK_SECRET = "your_webhook_secret"

func handleWebhook(w http.ResponseWriter, r *http.Request) {
	// Verify signature
	signature := r.Header.Get("X-Webhook-Signature")
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read body", http.StatusBadRequest)
		return
	}

	if !xagent.VerifyWebhookSignature(body, signature, WEBHOOK_SECRET) {
		http.Error(w, "Invalid signature", http.StatusUnauthorized)
		return
	}

	// Process event
	var event map[string]interface{}
	if err := json.Unmarshal(body, &event); err != nil {
		http.Error(w, "Failed to parse JSON", http.StatusBadRequest)
		return
	}

	fmt.Printf("Received event: %v\n", event["event_type"])

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func main() {
	http.HandleFunc("/webhooks/xagent", handleWebhook)
	log.Fatal(http.ListenAndServe(":8080", nil))
}
```

---

## Java Examples

### Installation

Add to `pom.xml`:

```xml
<dependency>
    <groupId>io.xagent</groupId>
    <artifactId>partner-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### Basic Usage

```java
import io.xagent.partner.*;
import java.time.Duration;

public class Example {
    public static void main(String[] args) throws PartnerAPIException {
        // Initialize client
        PartnerClient client = new PartnerClient(
            "xag_partner_xxx",
            "https://api.x-agent.io",
            Duration.ofSeconds(30),
            3
        );

        // Register partner
        PartnerClient.PartnerRegistrationRequest req = new PartnerClient.PartnerRegistrationRequest();
        req.companyName = "Acme Corp";
        req.contactEmail = "contact@acme.com";
        req.contactName = "John Doe";
        req.integrationType = "standard";

        PartnerClient.PartnerResponse partner = client.registerPartner(req);
        System.out.println("Partner registered: " + partner.partnerId);

        // Create API key
        PartnerClient.APIKeyRequest keyReq = new PartnerClient.APIKeyRequest();
        keyReq.name = "Production Key";
        keyReq.expiresInDays = 365;
        keyReq.rateLimitRpm = 1000;

        PartnerClient.APIKeyResponse apiKey = client.createAPIKey(partner.partnerId, keyReq);
        System.out.println("API key created: " + apiKey.keyPrefix);
        System.out.println("Full key (save securely): " + apiKey.key);

        // Get usage
        PartnerClient.UsageResponse usage = client.getUsage(partner.partnerId, "current_month", null, null);
        System.out.println("Usage: " + usage.totalRequests + " requests");
    }
}
```

### Webhook Integration

```java
import com.sun.net.httpserver.*;
import io.xagent.partner.*;
import java.io.*;
import java.net.InetSocketAddress;
import java.util.Map;

public class WebhookServer {
    private static final String WEBHOOK_SECRET = "your_webhook_secret";

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        server.createContext("/webhooks/xagent", WebhookServer::handleWebhook);
        server.start();
        System.out.println("Webhook server running on port 8080");
    }

    private static void handleWebhook(HttpExchange exchange) throws IOException {
        // Verify signature
        String signature = exchange.getRequestHeaders().getFirst("X-Webhook-Signature");
        byte[] body = exchange.getRequestBody().readAllBytes();

        if (!PartnerClient.verifyWebhookSignature(body, signature, WEBHOOK_SECRET)) {
            exchange.sendResponseHeaders(401, 0);
            exchange.close();
            return;
        }

        // Process event
        String bodyStr = new String(body);
        System.out.println("Received webhook: " + bodyStr);

        // Send response
        String response = "{\"status\": \"ok\"}";
        exchange.sendResponseHeaders(200, response.length());
        exchange.getResponseBody().write(response.getBytes());
        exchange.close();
    }
}
```

---

## Common Patterns

### Retry Logic

All SDKs implement automatic retry logic with exponential backoff:

- Retries on 5xx errors
- Retries on rate limit (429) with Retry-After header
- Configurable max retries (default: 3)

### Error Handling

All SDKs provide specific exception types:

- `PartnerAPIError`: Base exception
- `PartnerAuthError`: Authentication failed (401)
- `PartnerNotFoundError`: Resource not found (404)
- `PartnerRateLimitError`: Rate limit exceeded (429)

### Webhook Verification

All SDKs provide signature verification:

```
signature = HMAC-SHA256(request_body, webhook_secret)
```

Always verify signatures before processing webhooks.

### Rate Limiting

Monitor rate limit headers:

- `X-RateLimit-Limit`: Total requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Best Practices

1. **Store API Keys Securely**: Use environment variables, not hardcoded values
2. **Implement Retry Logic**: Use SDK's built-in retry mechanism
3. **Monitor Usage**: Check usage regularly to avoid quota issues
4. **Verify Webhooks**: Always verify webhook signatures
5. **Handle Errors**: Implement proper error handling and logging
6. **Rotate Keys**: Rotate API keys regularly (every 90 days)
7. **Use Scopes**: Create keys with minimal required scopes
8. **Test Webhooks**: Use test webhook feature before production

---

## Support

For questions or issues:

- **Documentation**: https://docs.x-agent.io/partners
- **Email**: partners@x-agent.io
- **GitHub Issues**: https://github.com/xagent/partner-sdk-*/issues
