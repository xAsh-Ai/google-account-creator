# 📚 Google Account Creator API Documentation

Complete API reference for the Google Account Creator system. This documentation covers all REST endpoints, WebSocket connections, data models, and usage examples.

## 📋 Table of Contents

- [🔑 Authentication](#-authentication)
- [📱 Accounts API](#-accounts-api)
- [🎮 Devices API](#-devices-api)
- [⚡ Performance API](#-performance-api)
- [💾 Configuration API](#-configuration-api)
- [📊 Analytics API](#-analytics-api)
- [🔍 Logging API](#-logging-api)
- [🔌 WebSocket Events](#-websocket-events)
- [📝 Data Models](#-data-models)
- [❌ Error Codes](#-error-codes)
- [💡 Usage Examples](#-usage-examples)

## 🔑 Authentication

### API Key Authentication

```http
Authorization: Bearer {api_key}
Content-Type: application/json
```

### Session-based Authentication

```http
Cookie: session_id={session_token}
Content-Type: application/json
```

### Generate API Key

```http
POST /api/auth/keys
```

**Request Body:**
```json
{
    "name": "My Integration",
    "permissions": ["accounts:read", "accounts:write", "devices:read"],
    "expires_in": 86400
}
```

**Response:**
```json
{
    "api_key": "gac_ak_1234567890abcdef",
    "expires_at": "2024-01-01T00:00:00Z",
    "permissions": ["accounts:read", "accounts:write", "devices:read"]
}
```

## 📱 Accounts API

### Create Account

Creates a new Google account using specified parameters.

```http
POST /api/accounts
```

**Request Body:**
```json
{
    "device_id": "device_001",
    "vpn_location": "US",
    "verification_method": "sms",
    "account_template": {
        "first_name": "John",
        "last_name": "Doe",
        "birth_year": 1990,
        "gender": "male"
    },
    "options": {
        "use_proxy": true,
        "screenshot_enabled": true,
        "human_like_delays": true
    }
}
```

**Response:**
```json
{
    "account_id": "acc_123456789",
    "status": "creating",
    "email": "john.doe.123@gmail.com",
    "password": "generated_password_123",
    "created_at": "2024-01-01T12:00:00Z",
    "device_id": "device_001",
    "verification": {
        "method": "sms",
        "phone_number": "+1234567890",
        "status": "pending"
    },
    "metadata": {
        "vpn_location": "US",
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0..."
    }
}
```

### Get Account

Retrieves detailed information about a specific account.

```http
GET /api/accounts/{account_id}
```

**Response:**
```json
{
    "account_id": "acc_123456789",
    "status": "active",
    "email": "john.doe.123@gmail.com",
    "created_at": "2024-01-01T12:00:00Z",
    "last_verified": "2024-01-01T12:05:00Z",
    "survival_days": 45,
    "verification": {
        "method": "sms",
        "phone_number": "+1234567890",
        "verified_at": "2024-01-01T12:03:00Z"
    },
    "usage_stats": {
        "login_count": 15,
        "last_login": "2024-01-15T10:30:00Z",
        "activity_score": 8.5
    },
    "health": {
        "status": "healthy",
        "warnings": [],
        "risk_score": 0.2
    }
}
```

### List Accounts

Retrieves a paginated list of accounts with filtering options.

```http
GET /api/accounts?status=active&limit=50&offset=0&sort=created_at&order=desc
```

**Query Parameters:**
- `status`: Filter by account status (`active`, `suspended`, `creating`, `failed`)
- `device_id`: Filter by device ID
- `created_after`: ISO 8601 timestamp
- `created_before`: ISO 8601 timestamp
- `limit`: Number of results (max 100, default 20)
- `offset`: Pagination offset
- `sort`: Sort field (`created_at`, `email`, `survival_days`)
- `order`: Sort order (`asc`, `desc`)

**Response:**
```json
{
    "accounts": [
        {
            "account_id": "acc_123456789",
            "email": "john.doe.123@gmail.com",
            "status": "active",
            "created_at": "2024-01-01T12:00:00Z",
            "survival_days": 45,
            "device_id": "device_001"
        }
    ],
    "pagination": {
        "total": 1250,
        "limit": 50,
        "offset": 0,
        "has_next": true,
        "has_prev": false
    }
}
```

### Update Account

Updates account metadata or status.

```http
PATCH /api/accounts/{account_id}
```

**Request Body:**
```json
{
    "status": "suspended",
    "notes": "Suspended due to unusual activity",
    "metadata": {
        "custom_field": "value"
    }
}
```

### Delete Account

Soft deletes an account (marks as deleted).

```http
DELETE /api/accounts/{account_id}
```

**Response:**
```json
{
    "message": "Account marked as deleted",
    "deleted_at": "2024-01-01T15:00:00Z"
}
```

### Batch Operations

#### Batch Create Accounts

```http
POST /api/accounts/batch
```

**Request Body:**
```json
{
    "count": 10,
    "device_ids": ["device_001", "device_002"],
    "template": {
        "verification_method": "sms",
        "vpn_location": "US",
        "options": {
            "use_proxy": true,
            "human_like_delays": true
        }
    }
}
```

**Response:**
```json
{
    "batch_id": "batch_123456",
    "status": "processing",
    "accounts_requested": 10,
    "estimated_completion": "2024-01-01T13:00:00Z"
}
```

#### Batch Status

```http
GET /api/accounts/batch/{batch_id}
```

**Response:**
```json
{
    "batch_id": "batch_123456",
    "status": "completed",
    "accounts_requested": 10,
    "accounts_created": 8,
    "accounts_failed": 2,
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:45:00Z",
    "results": [
        {
            "account_id": "acc_123456789",
            "status": "active",
            "email": "john.doe.123@gmail.com"
        }
    ]
}
```

## 🎮 Devices API

### List Devices

Retrieves all connected devices and their status.

```http
GET /api/devices
```

**Response:**
```json
{
    "devices": [
        {
            "device_id": "device_001",
            "serial": "ABC123DEF456",
            "model": "Samsung Galaxy S21",
            "android_version": "11",
            "status": "online",
            "last_seen": "2024-01-01T12:00:00Z",
            "performance": {
                "cpu_usage": 25.5,
                "memory_usage": 60.2,
                "temperature": 32.1,
                "battery_level": 85
            },
            "capabilities": {
                "adb_enabled": true,
                "root_access": false,
                "screen_resolution": "1080x2340",
                "density": 420
            },
            "current_task": {
                "type": "account_creation",
                "account_id": "acc_123456789",
                "started_at": "2024-01-01T11:55:00Z",
                "progress": 75
            }
        }
    ]
}
```

### Get Device

Retrieves detailed information about a specific device.

```http
GET /api/devices/{device_id}
```

### Device Actions

#### Execute ADB Command

```http
POST /api/devices/{device_id}/adb
```

**Request Body:**
```json
{
    "command": "shell getprop ro.build.version.release",
    "timeout": 30,
    "optimize": true
}
```

**Response:**
```json
{
    "command": "shell getprop ro.build.version.release",
    "output": "11",
    "exit_code": 0,
    "execution_time": 0.045,
    "optimized": true
}
```

#### Take Screenshot

```http
POST /api/devices/{device_id}/screenshot
```

**Request Body:**
```json
{
    "format": "png",
    "quality": 90,
    "crop": {
        "x": 0,
        "y": 0,
        "width": 1080,
        "height": 2340
    }
}
```

**Response:**
```json
{
    "screenshot_id": "screenshot_123456",
    "url": "/api/screenshots/screenshot_123456.png",
    "metadata": {
        "width": 1080,
        "height": 2340,
        "format": "png",
        "size_bytes": 245760
    }
}
```

#### Reboot Device

```http
POST /api/devices/{device_id}/reboot
```

#### Device Health Check

```http
GET /api/devices/{device_id}/health
```

**Response:**
```json
{
    "device_id": "device_001",
    "status": "healthy",
    "checks": {
        "adb_connection": "pass",
        "screen_responsive": "pass",
        "memory_available": "pass",
        "battery_level": "warning",
        "temperature": "pass"
    },
    "performance": {
        "response_time": 0.125,
        "success_rate": 98.5,
        "last_24h_tasks": 45
    },
    "recommendations": [
        "Consider charging device (battery at 15%)"
    ]
}
```

## ⚡ Performance API

### System Performance

Get overall system performance metrics.

```http
GET /api/performance
```

**Response:**
```json
{
    "timestamp": "2024-01-01T12:00:00Z",
    "system": {
        "cpu_usage": 45.2,
        "memory_usage": 68.5,
        "disk_usage": 25.0,
        "network_io": {
            "bytes_sent": 1048576,
            "bytes_received": 2097152
        }
    },
    "application": {
        "active_tasks": 5,
        "completed_tasks": 150,
        "failed_tasks": 3,
        "queue_size": 12,
        "average_task_time": 180.5
    },
    "cache": {
        "hit_rate": 92.5,
        "size_mb": 512,
        "evictions": 25
    },
    "database": {
        "connection_pool": {
            "active": 8,
            "idle": 2,
            "max": 20
        },
        "query_performance": {
            "average_time": 0.025,
            "slow_queries": 1
        }
    }
}
```

### Memory Analytics

Get detailed memory usage and optimization metrics.

```http
GET /api/performance/memory
```

**Response:**
```json
{
    "memory_stats": {
        "total_mb": 4096,
        "used_mb": 2048,
        "free_mb": 2048,
        "cached_mb": 512,
        "buffers_mb": 256
    },
    "optimization": {
        "memory_saved_mb": 512,
        "optimization_rate": 35.2,
        "leak_detection": {
            "objects_tracked": 15000,
            "potential_leaks": 2,
            "growth_rate": 0.5
        }
    },
    "garbage_collection": {
        "collections": 45,
        "time_spent": 0.125,
        "objects_collected": 50000
    }
}
```

### ADB Performance

Get ADB communication performance metrics.

```http
GET /api/performance/adb
```

**Response:**
```json
{
    "adb_performance": {
        "command_cache": {
            "hit_rate": 85.5,
            "size": 1000,
            "evictions": 50
        },
        "command_fusion": {
            "fused_commands": 250,
            "efficiency_gain": 40.2
        },
        "timing": {
            "average_response": 0.045,
            "p95_response": 0.125,
            "timeout_rate": 0.1
        },
        "optimization": {
            "speed_improvement": 58.3,
            "bandwidth_saved": 25.5
        }
    }
}
```

## 💾 Configuration API

### Get Configuration

Retrieve current system configuration.

```http
GET /api/config
```

**Response:**
```json
{
    "application": {
        "max_concurrent_devices": 5,
        "default_timeout": 30,
        "screenshots_enabled": true,
        "log_level": "INFO"
    },
    "performance": {
        "memory_limit_mb": 2048,
        "cache_ttl": 3600,
        "optimization_enabled": true
    },
    "devices": {
        "auto_detect": true,
        "health_check_interval": 60,
        "max_retries": 3
    },
    "accounts": {
        "verification_timeout": 300,
        "batch_size": 10,
        "survival_tracking": true
    }
}
```

### Update Configuration

Update system configuration settings.

```http
PATCH /api/config
```

**Request Body:**
```json
{
    "performance": {
        "memory_limit_mb": 4096,
        "cache_ttl": 7200
    },
    "devices": {
        "max_retries": 5
    }
}
```

### Reset Configuration

Reset configuration to defaults.

```http
POST /api/config/reset
```

## 📊 Analytics API

### Account Analytics

Get detailed analytics about account creation and performance.

```http
GET /api/analytics/accounts
```

**Query Parameters:**
- `period`: Time period (`1h`, `24h`, `7d`, `30d`)
- `device_id`: Filter by device
- `status`: Filter by account status

**Response:**
```json
{
    "period": "24h",
    "summary": {
        "accounts_created": 150,
        "success_rate": 92.0,
        "average_creation_time": 180.5,
        "survival_rate": 88.5
    },
    "timeline": [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "accounts_created": 12,
            "success_rate": 91.7,
            "average_time": 175.2
        }
    ],
    "breakdown": {
        "by_device": {
            "device_001": {
                "accounts": 50,
                "success_rate": 94.0
            }
        },
        "by_verification": {
            "sms": {
                "accounts": 120,
                "success_rate": 93.3
            }
        },
        "by_location": {
            "US": {
                "accounts": 80,
                "success_rate": 90.0
            }
        }
    }
}
```

### Performance Analytics

Get performance analytics and trends.

```http
GET /api/analytics/performance
```

**Response:**
```json
{
    "period": "24h",
    "system_performance": {
        "cpu_usage": {
            "average": 45.2,
            "peak": 85.5,
            "trend": "stable"
        },
        "memory_usage": {
            "average": 2048,
            "peak": 3072,
            "optimization_savings": 512
        }
    },
    "optimization_impact": {
        "adb_speed_improvement": 58.3,
        "memory_reduction": 35.2,
        "cache_efficiency": 92.5
    },
    "alerts": [
        {
            "type": "warning",
            "message": "Memory usage approaching limit",
            "threshold": 3584,
            "current": 3200
        }
    ]
}
```

## 🔍 Logging API

### Get Logs

Retrieve application logs with filtering and pagination.

```http
GET /api/logs
```

**Query Parameters:**
- `level`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `component`: Component name (`adb_controller`, `account_creator`, etc.)
- `start_time`: ISO 8601 timestamp
- `end_time`: ISO 8601 timestamp
- `limit`: Number of results (max 1000, default 100)
- `offset`: Pagination offset

**Response:**
```json
{
    "logs": [
        {
            "timestamp": "2024-01-01T12:00:00.123Z",
            "level": "INFO",
            "component": "account_creator",
            "message": "Account creation started",
            "metadata": {
                "account_id": "acc_123456789",
                "device_id": "device_001",
                "request_id": "req_123456"
            }
        }
    ],
    "pagination": {
        "total": 5000,
        "limit": 100,
        "offset": 0,
        "has_next": true
    }
}
```

### Log Streaming

Stream real-time logs via WebSocket.

```http
GET /api/logs/stream
```

**WebSocket Messages:**
```json
{
    "type": "log",
    "data": {
        "timestamp": "2024-01-01T12:00:00.123Z",
        "level": "INFO",
        "component": "adb_controller",
        "message": "Device connected",
        "metadata": {
            "device_id": "device_001"
        }
    }
}
```

## 🔌 WebSocket Events

### Connection

Connect to the WebSocket endpoint for real-time updates.

```http
GET /api/ws
```

**Authentication:**
```
Authorization: Bearer {api_key}
```

### Event Types

#### Account Events

```json
{
    "type": "account_created",
    "data": {
        "account_id": "acc_123456789",
        "email": "john.doe.123@gmail.com",
        "status": "active",
        "device_id": "device_001"
    }
}
```

```json
{
    "type": "account_status_changed",
    "data": {
        "account_id": "acc_123456789",
        "old_status": "creating",
        "new_status": "active",
        "timestamp": "2024-01-01T12:00:00Z"
    }
}
```

#### Device Events

```json
{
    "type": "device_connected",
    "data": {
        "device_id": "device_001",
        "model": "Samsung Galaxy S21",
        "status": "online"
    }
}
```

```json
{
    "type": "device_performance",
    "data": {
        "device_id": "device_001",
        "cpu_usage": 45.2,
        "memory_usage": 60.1,
        "battery_level": 75
    }
}
```

#### System Events

```json
{
    "type": "system_performance",
    "data": {
        "cpu_usage": 45.2,
        "memory_usage": 2048,
        "active_tasks": 5
    }
}
```

```json
{
    "type": "alert",
    "data": {
        "level": "warning",
        "message": "High memory usage detected",
        "component": "memory_optimizer",
        "timestamp": "2024-01-01T12:00:00Z"
    }
}
```

### Subscribe to Events

Subscribe to specific event types:

```json
{
    "action": "subscribe",
    "events": ["account_created", "device_performance"],
    "filters": {
        "device_id": "device_001"
    }
}
```

## 📝 Data Models

### Account Model

```json
{
    "account_id": "string",
    "email": "string",
    "password": "string",
    "status": "creating|active|suspended|failed|deleted",
    "created_at": "datetime",
    "last_verified": "datetime",
    "survival_days": "integer",
    "device_id": "string",
    "verification": {
        "method": "sms|email|voice",
        "phone_number": "string",
        "verified_at": "datetime",
        "attempts": "integer"
    },
    "metadata": {
        "vpn_location": "string",
        "ip_address": "string",
        "user_agent": "string",
        "first_name": "string",
        "last_name": "string",
        "birth_year": "integer",
        "gender": "string"
    },
    "usage_stats": {
        "login_count": "integer",
        "last_login": "datetime",
        "activity_score": "float"
    },
    "health": {
        "status": "healthy|warning|critical",
        "warnings": ["string"],
        "risk_score": "float"
    }
}
```

### Device Model

```json
{
    "device_id": "string",
    "serial": "string",
    "model": "string",
    "manufacturer": "string",
    "android_version": "string",
    "status": "online|offline|busy|error",
    "last_seen": "datetime",
    "performance": {
        "cpu_usage": "float",
        "memory_usage": "float",
        "temperature": "float",
        "battery_level": "integer"
    },
    "capabilities": {
        "adb_enabled": "boolean",
        "root_access": "boolean",
        "screen_resolution": "string",
        "density": "integer"
    },
    "current_task": {
        "type": "string",
        "account_id": "string",
        "started_at": "datetime",
        "progress": "integer"
    }
}
```

### Performance Model

```json
{
    "timestamp": "datetime",
    "system": {
        "cpu_usage": "float",
        "memory_usage": "float",
        "disk_usage": "float",
        "network_io": {
            "bytes_sent": "integer",
            "bytes_received": "integer"
        }
    },
    "application": {
        "active_tasks": "integer",
        "completed_tasks": "integer",
        "failed_tasks": "integer",
        "queue_size": "integer",
        "average_task_time": "float"
    },
    "optimization": {
        "memory_saved_mb": "integer",
        "adb_speed_improvement": "float",
        "cache_hit_rate": "float"
    }
}
```

## ❌ Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Application Error Codes

```json
{
    "error": {
        "code": "DEVICE_NOT_FOUND",
        "message": "Device with ID 'device_001' not found",
        "details": {
            "device_id": "device_001",
            "available_devices": ["device_002", "device_003"]
        },
        "timestamp": "2024-01-01T12:00:00Z",
        "request_id": "req_123456"
    }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `DEVICE_NOT_FOUND` | Device not found or offline |
| `ACCOUNT_CREATION_FAILED` | Account creation process failed |
| `INVALID_DEVICE_STATE` | Device in invalid state for operation |
| `SMS_VERIFICATION_TIMEOUT` | SMS verification timed out |
| `RATE_LIMIT_EXCEEDED` | API rate limit exceeded |
| `INSUFFICIENT_RESOURCES` | System resources exhausted |
| `CONFIGURATION_ERROR` | Invalid configuration detected |
| `ADB_COMMAND_FAILED` | ADB command execution failed |
| `OPTIMIZATION_ERROR` | Performance optimization error |

## 💡 Usage Examples

### Python SDK Example

```python
import asyncio
from google_account_creator_sdk import GoogleAccountCreatorClient

# Initialize client
client = GoogleAccountCreatorClient(
    base_url="http://localhost:8080",
    api_key="gac_ak_1234567890abcdef"
)

async def create_account_example():
    # Create account
    account = await client.accounts.create(
        device_id="device_001",
        vpn_location="US",
        verification_method="sms"
    )
    
    print(f"Created account: {account.email}")
    
    # Monitor progress
    async for event in client.websocket.listen():
        if event.type == "account_created" and event.data.account_id == account.account_id:
            print(f"Account {account.email} is now active!")
            break

# Run example
asyncio.run(create_account_example())
```

### cURL Examples

#### Create Account

```bash
curl -X POST http://localhost:8080/api/accounts \
  -H "Authorization: Bearer gac_ak_1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device_001",
    "vpn_location": "US",
    "verification_method": "sms"
  }'
```

#### Get Device Status

```bash
curl -X GET http://localhost:8080/api/devices/device_001 \
  -H "Authorization: Bearer gac_ak_1234567890abcdef"
```

#### Stream Logs

```bash
curl -N http://localhost:8080/api/logs/stream \
  -H "Authorization: Bearer gac_ak_1234567890abcdef"
```

### JavaScript/Node.js Example

```javascript
const { GoogleAccountCreatorClient } = require('google-account-creator-sdk');

const client = new GoogleAccountCreatorClient({
    baseURL: 'http://localhost:8080',
    apiKey: 'gac_ak_1234567890abcdef'
});

// Create account
async function createAccount() {
    try {
        const account = await client.accounts.create({
            deviceId: 'device_001',
            vpnLocation: 'US',
            verificationMethod: 'sms'
        });
        
        console.log(`Created account: ${account.email}`);
        return account;
    } catch (error) {
        console.error('Account creation failed:', error.message);
    }
}

// Monitor performance
async function monitorPerformance() {
    const performance = await client.performance.get();
    console.log(`CPU Usage: ${performance.system.cpu_usage}%`);
    console.log(`Memory Usage: ${performance.system.memory_usage}%`);
}

// Real-time updates
client.websocket.on('account_created', (event) => {
    console.log(`New account created: ${event.data.email}`);
});

client.websocket.on('device_performance', (event) => {
    console.log(`Device ${event.data.device_id} performance updated`);
});
```

---

## 📞 Support

For API support and questions:

- **📚 Documentation**: [https://docs.google-account-creator.com](https://docs.google-account-creator.com)
- **🐛 Issues**: [GitHub Issues](https://github.com/your-org/google-account-creator/issues)
- **💬 Discord**: [Join our Discord server](https://discord.gg/google-account-creator)
- **📧 Email**: [api-support@google-account-creator.com](mailto:api-support@google-account-creator.com)

---

<div align="center">

**🔗 [Back to Main Documentation](../README.md)**

</div> 