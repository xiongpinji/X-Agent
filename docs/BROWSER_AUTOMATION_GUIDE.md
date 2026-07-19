"""
Troubleshooting guide and configuration documentation for enhanced browser automation.
"""

# ============================================================================
# TROUBLESHOOTING GUIDE
# ============================================================================

TROUBLESHOOTING_GUIDE = """
# Enhanced Browser Automation - Troubleshooting Guide

## Common Issues and Solutions

### 1. Element Not Found Errors

**Problem**: SmartLocator cannot find elements even though they exist on the page.

**Causes**:
- Element is not yet loaded (timing issue)
- Element is hidden or not visible
- Selector is incorrect or has changed
- Element is inside an iframe

**Solutions**:
1. Use adaptive waiting strategy:
   ```python
   result = await waiter.wait_for_selector(
       page,
       selector,
       strategy=WaitStrategy.ADAPTIVE,
   )
   ```

2. Try multiple locator strategies:
   ```python
   result = locator.find_element(
       strategies=[
           LocatorStrategy.CSS,
           LocatorStrategy.XPATH,
           LocatorStrategy.TEXT,
       ],
       css_selector=".button",
       xpath="//button",
       text="Click me",
   )
   ```

3. Check if element is in iframe:
   ```python
   frame = await interactions.handle_iframe(page, "iframe#content")
   if frame:
       # Interact with frame content
       pass
   ```

4. Increase wait timeout:
   ```python
   result = await waiter.wait_for_selector(
       page,
       selector,
       timeout=60.0,  # Increase timeout
   )
   ```

### 2. Timeout Errors

**Problem**: Operations timeout frequently.

**Causes**:
- Page is slow to load
- Network issues
- Timeout value is too low
- Page has infinite loading state

**Solutions**:
1. Increase default timeout:
   ```python
   service = EnhancedBrowserAutomationService(
       default_timeout=60.0,  # Increase from 30s
   )
   ```

2. Use adaptive waiting:
   ```python
   result = await waiter.wait_for_page_stable(
       page,
       timeout=60.0,
       stability_threshold=2.0,
   )
   ```

3. Check network idle:
   ```python
   result = await waiter.wait_for_network_idle(page)
   if not result.success:
       # Network still active, try again
       pass
   ```

4. Monitor wait statistics:
   ```python
   stats = waiter.get_wait_stats()
   print(f"Average wait: {stats['average_wait_ms']}ms")
   print(f"Max wait: {stats['max_wait_ms']}ms")
   ```

### 3. CAPTCHA Detection

**Problem**: Automation stops when CAPTCHA is encountered.

**Causes**:
- Site has CAPTCHA protection
- Bot detection triggered

**Solutions**:
1. Detect CAPTCHA early:
   ```python
   has_captcha = await recovery.detect_captcha(page)
   if has_captcha:
       # Handle CAPTCHA (manual intervention or service)
       print("CAPTCHA detected, manual intervention required")
   ```

2. Use stealth mode:
   ```python
   service = EnhancedBrowserAutomationService(enable_stealth=True)
   ```

3. Add human-like delays:
   ```python
   await stealth.simulate_human_behavior(page)
   await stealth.add_delay_between_actions(1.0, 3.0)
   ```

4. Randomize user agent:
   ```python
   ua = stealth.get_random_user_agent()
   print(f"Using: {ua.browser} on {ua.os}")
   ```

### 4. Login Required Errors

**Problem**: Automation encounters login pages unexpectedly.

**Causes**:
- Session expired
- Cookies cleared
- Authentication required

**Solutions**:
1. Detect login requirement:
   ```python
   login_required = await recovery.detect_login_required(page)
   if login_required:
       # Handle login
       pass
   ```

2. Preserve cookies:
   ```python
   # Save cookies after login
   cookies = await context.cookies()
   
   # Restore cookies in new session
   await context.add_cookies(cookies)
   ```

3. Implement login flow:
   ```python
   async def login(page, username, password):
       await page.fill("input[name='username']", username)
       await page.fill("input[name='password']", password)
       await page.click("button[type='submit']")
       await page.wait_for_load_state("networkidle")
   ```

### 5. Page Crash or Navigation Errors

**Problem**: Page crashes or navigation fails.

**Causes**:
- Server error (500, 502, 503)
- Network connectivity issue
- Page has JavaScript errors

**Solutions**:
1. Detect page crash:
   ```python
   page_crashed = await recovery.detect_page_crash(page)
   if page_crashed:
       # Reload or navigate to home
       await page.goto("/")
   ```

2. Handle navigation errors:
   ```python
   try:
       await page.goto(url)
   except Exception as e:
       if "net::ERR_CONNECTION_REFUSED" in str(e):
           # Network error, retry
           await asyncio.sleep(5)
           await page.goto(url)
   ```

3. Use error recovery:
   ```python
   success = await recovery.handle_network_error(page, retry_count=3)
   if not success:
       # Give up or escalate
       pass
   ```

### 6. Interaction Failures

**Problem**: Clicks, fills, or other interactions fail.

**Causes**:
- Element not visible
- Element is disabled
- Element moved or changed
- JavaScript event handlers not ready

**Solutions**:
1. Scroll element into view:
   ```python
   result = await interactions.scroll_to_element(page, selector)
   ```

2. Wait for element to be visible:
   ```python
   await page.locator(selector).wait_for(state="visible")
   ```

3. Retry interaction:
   ```python
   success = await recovery.retry_operation(
       lambda: interactions.double_click(page, selector),
       max_retries=3,
   )
   ```

4. Check element state:
   ```python
   is_visible = await page.locator(selector).is_visible()
   is_enabled = await page.locator(selector).is_enabled()
   ```

### 7. Memory Leaks or Resource Issues

**Problem**: Memory usage grows over time or browser crashes.

**Causes**:
- Sessions not properly closed
- Browser pool not cleaning up
- Too many concurrent browsers

**Solutions**:
1. Always cleanup:
   ```python
   try:
       # Use service
       pass
   finally:
       await service.cleanup()
   ```

2. Monitor pool health:
   ```python
   stats = pool.get_stats()
   print(f"Active browsers: {stats.active_browsers}")
   print(f"Idle browsers: {stats.idle_browsers}")
   ```

3. Cleanup idle browsers:
   ```python
   closed = await pool.cleanup_idle_browsers()
   print(f"Closed {closed} idle browsers")
   ```

4. Limit concurrent browsers:
   ```python
   pool = create_browser_pool("main", max_browsers=5)
   ```

### 8. Slow Performance

**Problem**: Automation is slower than expected.

**Causes**:
- Inefficient wait strategies
- Too many retries
- Unnecessary delays
- Poor element locating

**Solutions**:
1. Optimize wait strategy:
   ```python
   # Use specific strategy instead of adaptive
   result = await waiter.wait_for_selector(
       page,
       selector,
       strategy=WaitStrategy.DOM_CONTENT,  # Faster than ADAPTIVE
   )
   ```

2. Cache element locations:
   ```python
   result = locator.find_element(
       css_selector=".button",
       use_cache=True,  # Reuse cached results
   )
   ```

3. Reduce delays:
   ```python
   # Only add delays when necessary
   if needs_human_simulation:
       await stealth.add_delay_between_actions(0.5, 1.0)
   ```

4. Monitor performance:
   ```python
   stats = service.get_session_stats(session_id)
   print(f"Average action time: {stats['action_count']} actions")
   ```

### 9. Stealth Mode Not Working

**Problem**: Bot detection still occurs even with stealth mode enabled.

**Causes**:
- Stealth measures incomplete
- Site uses advanced detection
- User agent still detected as bot

**Solutions**:
1. Verify stealth is applied:
   ```python
   success = await stealth.apply_stealth_measures(page)
   if not success:
       print("Stealth measures failed")
   ```

2. Use all stealth options:
   ```python
   context_options = stealth.get_stealth_context_options()
   launch_options = stealth.get_stealth_launch_options()
   ```

3. Randomize everything:
   ```python
   ua = stealth.get_random_user_agent()
   viewport = stealth.get_random_viewport()
   locale = stealth.get_random_locale()
   ```

4. Add human behavior:
   ```python
   await stealth.simulate_human_behavior(page)
   ```

### 10. Debugging Tips

**Enable Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Take Screenshots on Error**:
```python
try:
    # Operation
    pass
except Exception as e:
    await page.screenshot(path=f"/tmp/error_{int(time.time())}.png")
    raise
```

**Monitor Statistics**:
```python
stats = service.get_session_stats(session_id)
print(f"Actions: {stats['action_count']}")
print(f"Errors: {stats['error_count']}")
print(f"Wait stats: {stats['waiter_stats']}")
```

**Check Page State**:
```python
url = page.url
title = await page.title()
content = await page.content()
print(f"URL: {url}, Title: {title}")
```

---

## Performance Optimization Tips

1. **Use Browser Pool**: Reuse browsers for multiple sessions
2. **Cache Elements**: Enable caching for frequently accessed elements
3. **Optimize Waits**: Use specific wait strategies instead of adaptive
4. **Batch Operations**: Group related operations together
5. **Monitor Metrics**: Track performance metrics and optimize based on data
6. **Reduce Delays**: Only add delays when necessary for human simulation
7. **Cleanup Resources**: Regularly cleanup idle browsers and sessions
8. **Use Stealth Wisely**: Only enable stealth when needed (performance cost)

---

## Configuration Best Practices

1. **Timeout Values**:
   - Default: 30 seconds
   - Dynamic content: 60 seconds
   - Slow sites: 120 seconds

2. **Retry Settings**:
   - Max retries: 3
   - Initial delay: 1-2 seconds
   - Use exponential backoff

3. **Pool Settings**:
   - Max browsers: 5-10 (depends on system)
   - Idle timeout: 60 seconds
   - Session limit: 10 per browser

4. **Stealth Settings**:
   - Enable for bot-protected sites
   - Disable for trusted sites (performance)
   - Randomize user agents

5. **Wait Strategies**:
   - Adaptive: General purpose
   - Network idle: After navigation
   - DOM content: Fast pages
   - Custom: Specific conditions
"""


# ============================================================================
# CONFIGURATION GUIDE
# ============================================================================

CONFIGURATION_GUIDE = """
# Enhanced Browser Automation - Configuration Guide

## Service Configuration

### Basic Configuration
```python
from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService

service = EnhancedBrowserAutomationService(
    pool_size=5,              # Number of browser instances
    default_timeout=30.0,     # Default timeout in seconds
    enable_stealth=True,      # Enable stealth mode
)
```

### Advanced Configuration

#### SmartLocator Configuration
```python
from backend.app.services.browser.smart_locator import SmartLocator

locator = SmartLocator(
    session_id="session_1",
    max_retries=3,            # Retry attempts
    retry_delay_ms=500,       # Delay between retries
    enable_ai_fallback=True,  # Enable AI detection fallback
)
```

#### SmartWaiter Configuration
```python
from backend.app.services.browser.waiter import SmartWaiter

waiter = SmartWaiter(
    session_id="session_1",
    default_timeout=30.0,           # Default timeout
    adaptive_timeout=True,          # Enable adaptive timeout
    network_idle_timeout=2.0,       # Network idle detection timeout
)
```

#### BrowserPool Configuration
```python
from backend.app.services.browser.pool import create_browser_pool

pool = create_browser_pool(
    pool_id="main_pool",
    max_browsers=5,                 # Maximum browser instances
    max_sessions_per_browser=10,    # Sessions per browser
    browser_timeout=300.0,          # Browser timeout
    idle_timeout=60.0,              # Idle browser timeout
)
```

#### StealthBrowser Configuration
```python
from backend.app.services.browser.stealth import StealthBrowser

stealth = StealthBrowser("session_1")

# Get stealth options
context_options = stealth.get_stealth_context_options()
launch_options = stealth.get_stealth_launch_options()

# Create browser with stealth
browser = await playwright.chromium.launch(**launch_options)
context = await browser.new_context(**context_options)
```

## Environment Variables

```bash
# Browser automation settings
BROWSER_POOL_SIZE=5
BROWSER_DEFAULT_TIMEOUT=30
BROWSER_ENABLE_STEALTH=true
BROWSER_HEADLESS=true

# Locator settings
LOCATOR_MAX_RETRIES=3
LOCATOR_RETRY_DELAY_MS=500
LOCATOR_ENABLE_AI=true

# Waiter settings
WAITER_DEFAULT_TIMEOUT=30
WAITER_ADAPTIVE_TIMEOUT=true
WAITER_NETWORK_IDLE_TIMEOUT=2

# Pool settings
POOL_MAX_BROWSERS=5
POOL_MAX_SESSIONS_PER_BROWSER=10
POOL_IDLE_TIMEOUT=60

# Stealth settings
STEALTH_ENABLED=true
STEALTH_RANDOMIZE_UA=true
STEALTH_RANDOMIZE_VIEWPORT=true
```

## Logging Configuration

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('browser_automation.log'),
        logging.StreamHandler(),
    ]
)

# Set specific loggers
logging.getLogger('backend.app.services.browser').setLevel(logging.DEBUG)
```

## Performance Tuning

### For High-Speed Automation
```python
service = EnhancedBrowserAutomationService(
    pool_size=10,
    default_timeout=15.0,
    enable_stealth=False,  # Disable stealth for speed
)

waiter = SmartWaiter(
    default_timeout=15.0,
    adaptive_timeout=False,  # Use specific strategies
)
```

### For Reliable Automation
```python
service = EnhancedBrowserAutomationService(
    pool_size=3,
    default_timeout=60.0,
    enable_stealth=True,
)

waiter = SmartWaiter(
    default_timeout=60.0,
    adaptive_timeout=True,  # Use adaptive waiting
)
```

### For Bot-Protected Sites
```python
service = EnhancedBrowserAutomationService(
    pool_size=2,
    default_timeout=45.0,
    enable_stealth=True,
)

stealth = StealthBrowser("session_1")
await stealth.apply_stealth_measures(page)
await stealth.simulate_human_behavior(page)
```

## Resource Limits

### Memory Management
```python
# Limit concurrent browsers
pool = create_browser_pool("main", max_browsers=5)

# Cleanup idle browsers
await pool.cleanup_idle_browsers()

# Monitor memory
stats = pool.get_stats()
print(f"Active browsers: {stats.active_browsers}")
```

### Timeout Management
```python
# Set appropriate timeouts
waiter = SmartWaiter(
    default_timeout=30.0,  # 30 seconds
)

# Override for specific operations
result = await waiter.wait_for_selector(
    page,
    selector,
    timeout=60.0,  # 60 seconds for this operation
)
```

## Error Handling Configuration

```python
from backend.app.services.browser.recovery import ErrorRecovery, ErrorType

recovery = ErrorRecovery("session_1")

# Register custom handlers
async def handle_timeout(session_id, error):
    print(f"Timeout in session {session_id}")

recovery.register_error_handler(ErrorType.TIMEOUT, handle_timeout)

# Configure retry behavior
recovery.max_retries = 3
recovery.retry_delay = 2.0
```

## Monitoring and Metrics

```python
# Get session statistics
stats = service.get_session_stats(session_id)
print(f"Actions: {stats['action_count']}")
print(f"Errors: {stats['error_count']}")
print(f"Uptime: {stats['uptime']}s")

# Get pool statistics
pool_stats = service.get_pool_stats()
for pool_id, stats in pool_stats.items():
    print(f"Pool {pool_id}: {stats['active_browsers']} active")

# Get component statistics
print(f"Locator cache: {stats['locator_stats']}")
print(f"Wait stats: {stats['waiter_stats']}")
print(f"Interaction stats: {stats['interaction_stats']}")
print(f"Error stats: {stats['error_stats']}")
```

## Integration with Existing Code

```python
# Replace old automation service
from backend.app.services.browser.enhanced_service import get_enhanced_automation_service

# Get global instance
service = get_enhanced_automation_service()

# Or create new instance
from backend.app.services.browser.enhanced_service import EnhancedBrowserAutomationService
service = EnhancedBrowserAutomationService()

# Use with existing code
session = await service.create_session("session_1", page)
await service.navigate(session.session_id, url)
```
"""


if __name__ == "__main__":
    print(TROUBLESHOOTING_GUIDE)
    print("\n" + "="*80 + "\n")
    print(CONFIGURATION_GUIDE)
