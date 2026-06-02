# X-Agent Desktop 测试用例

## 单元测试

### 文件操作测试

```rust
#[cfg(test)]
mod file_tests {
    use super::*;

    #[tokio::test]
    async fn test_read_file() {
        // 创建测试文件
        let test_file = "/tmp/test.txt";
        std::fs::write(test_file, "Hello, World!").unwrap();

        // 测试读取
        let content = read_file(test_file.to_string()).await;
        assert!(content.is_ok());
        assert_eq!(content.unwrap(), "Hello, World!");

        // 清理
        std::fs::remove_file(test_file).unwrap();
    }

    #[tokio::test]
    async fn test_write_file() {
        let test_file = "/tmp/test_write.txt";
        let content = "Test content";

        let result = write_file(test_file.to_string(), content.to_string()).await;
        assert!(result.is_ok());

        let read_content = std::fs::read_to_string(test_file).unwrap();
        assert_eq!(read_content, content);

        std::fs::remove_file(test_file).unwrap();
    }

    #[tokio::test]
    async fn test_list_directory() {
        let test_dir = "/tmp/test_dir";
        std::fs::create_dir_all(test_dir).unwrap();
        std::fs::write(format!("{}/file1.txt", test_dir), "content1").unwrap();
        std::fs::write(format!("{}/file2.txt", test_dir), "content2").unwrap();

        let result = list_directory(test_dir.to_string()).await;
        assert!(result.is_ok());
        assert_eq!(result.unwrap().len(), 2);

        std::fs::remove_dir_all(test_dir).unwrap();
    }

    #[tokio::test]
    async fn test_path_traversal_prevention() {
        let base_dir = "/home/user";
        let malicious_path = "/home/user/../../etc/passwd";

        let result = validate_file_path(
            std::path::Path::new(base_dir),
            std::path::Path::new(malicious_path)
        );
        assert!(result.is_err());
    }
}
```

### 安全测试

```rust
#[cfg(test)]
mod security_tests {
    use super::*;

    #[test]
    fn test_encryption_decryption() {
        let encryption = Encryption::from_password("test_password");
        let plaintext = b"Sensitive data";

        let ciphertext = encryption.encrypt(plaintext).unwrap();
        let decrypted = encryption.decrypt(&ciphertext).unwrap();

        assert_eq!(plaintext, &decrypted[..]);
    }

    #[test]
    fn test_encryption_different_passwords() {
        let enc1 = Encryption::from_password("password1");
        let enc2 = Encryption::from_password("password2");
        let plaintext = b"Test";

        let ciphertext = enc1.encrypt(plaintext).unwrap();
        let result = enc2.decrypt(&ciphertext);

        assert!(result.is_err());
    }

    #[test]
    fn test_safe_filename() {
        assert!(is_safe_filename("document.txt"));
        assert!(is_safe_filename("my-file_2024.pdf"));
        assert!(!is_safe_filename("../etc/passwd"));
        assert!(!is_safe_filename("..\\windows\\system32"));
        assert!(!is_safe_filename("file\x00name"));
    }

    #[test]
    fn test_path_validation() {
        let base = std::path::Path::new("/home/user");
        let safe_path = std::path::Path::new("/home/user/documents/file.txt");
        let unsafe_path = std::path::Path::new("/etc/passwd");

        assert!(validate_file_path(base, safe_path).is_ok());
        assert!(validate_file_path(base, unsafe_path).is_err());
    }
}
```

## 集成测试

### 后端通信测试

```rust
#[cfg(test)]
mod integration_tests {
    use super::*;

    #[tokio::test]
    async fn test_backend_connection() {
        // 模拟后端服务
        let app_handle = create_test_app_handle();

        let result = connect_to_backend(&app_handle).await;
        // 根据后端可用性判断
        // assert!(result.is_ok() || result.is_err());
    }

    #[tokio::test]
    async fn test_api_call() {
        let app_handle = create_test_app_handle();

        let result = call_backend_api(
            &app_handle,
            "GET",
            "/api/agents",
            None
        ).await;

        // 验证响应格式
        if let Ok(response) = result {
            assert!(response.is_object());
        }
    }

    #[tokio::test]
    async fn test_agent_lifecycle() {
        let app_handle = create_test_app_handle();

        // 启动Agent
        let start_result = start_agent("test-agent".to_string(), app_handle.clone()).await;
        assert!(start_result.is_ok());

        // 获取状态
        let status_result = get_agent_status("test-agent".to_string(), app_handle.clone()).await;
        assert!(status_result.is_ok());

        // 停止Agent
        let stop_result = stop_agent("test-agent".to_string(), app_handle.clone()).await;
        assert!(stop_result.is_ok());
    }
}
```

## 前端测试

### 组件测试

```typescript
// tests/Home.spec.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import Home from '@/views/Home.vue'

describe('Home Component', () => {
  let wrapper

  beforeEach(() => {
    wrapper = mount(Home)
  })

  it('renders home page', () => {
    expect(wrapper.find('.home-page').exists()).toBe(true)
  })

  it('displays statistics cards', () => {
    const cards = wrapper.findAll('.stat-card')
    expect(cards.length).toBeGreaterThan(0)
  })

  it('loads dashboard data on mount', async () => {
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.runningAgents).toBeGreaterThanOrEqual(0)
  })

  it('handles quick actions', async () => {
    const button = wrapper.find('button')
    await button.trigger('click')
    // 验证事件处理
  })
})
```

### API调用测试

```typescript
// tests/api.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { invoke } from '@tauri-apps/api/tauri'

vi.mock('@tauri-apps/api/tauri')

describe('API Calls', () => {
  it('calls backend API successfully', async () => {
    vi.mocked(invoke).mockResolvedValue({ status: 'ok' })

    const result = await invoke('call_backend_api', {
      method: 'GET',
      path: '/api/agents'
    })

    expect(result.status).toBe('ok')
  })

  it('handles API errors', async () => {
    vi.mocked(invoke).mockRejectedValue(new Error('API Error'))

    try {
      await invoke('call_backend_api', {
        method: 'GET',
        path: '/api/agents'
      })
    } catch (e) {
      expect(e.message).toBe('API Error')
    }
  })
})
```

## E2E测试

### 用户流程测试

```typescript
// tests/e2e/user-flow.spec.ts
import { test, expect } from '@playwright/test'

test.describe('User Flow', () => {
  test('complete agent workflow', async ({ page }) => {
    // 打开应用
    await page.goto('http://localhost:5173')

    // 验证首页加载
    await expect(page.locator('.home-page')).toBeVisible()

    // 导航到Agent管理
    await page.click('a[href="/agents"]')
    await expect(page.locator('.agents-page')).toBeVisible()

    // 创建Agent
    await page.click('button:has-text("新建Agent")')
    await page.fill('input[placeholder="Agent名称"]', 'Test Agent')
    await page.click('button:has-text("创建")')

    // 验证Agent已创建
    await expect(page.locator('text=Test Agent')).toBeVisible()

    // 启动Agent
    await page.click('button:has-text("启动")')
    await expect(page.locator('text=运行中')).toBeVisible()

    // 停止Agent
    await page.click('button:has-text("停止")')
    await expect(page.locator('text=已停止')).toBeVisible()
  })

  test('file browser workflow', async ({ page }) => {
    await page.goto('http://localhost:5173')

    // 导航到文件浏览
    await page.click('a[href="/files"]')
    await expect(page.locator('.files-page')).toBeVisible()

    // 创建文件夹
    await page.click('button:has-text("新建文件夹")')
    await page.fill('input[placeholder="文件夹名称"]', 'test-folder')
    await page.click('button:has-text("创建")')

    // 验证文件夹已创建
    await expect(page.locator('text=test-folder')).toBeVisible()

    // 删除文件夹
    await page.click('button:has-text("删除")')
    await page.click('button:has-text("确定")')

    // 验证文件夹已删除
    await expect(page.locator('text=test-folder')).not.toBeVisible()
  })

  test('settings workflow', async ({ page }) => {
    await page.goto('http://localhost:5173')

    // 导航到设置
    await page.click('a[href="/settings"]')
    await expect(page.locator('.settings-page')).toBeVisible()

    // 修改主题
    await page.selectOption('select', 'dark')
    await page.click('button:has-text("保存设置")')

    // 验证主题已更改
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  })
})
```

## 性能测试

### 启动时间测试

```rust
#[test]
fn test_startup_time() {
    let start = std::time::Instant::now();
    
    // 启动应用
    let _app = create_test_app();
    
    let duration = start.elapsed();
    
    // 验证启动时间 < 2秒
    assert!(duration.as_secs() < 2);
}
```

### 内存使用测试

```rust
#[test]
fn test_memory_usage() {
    // 获取初始内存
    let initial_memory = get_memory_usage();
    
    // 执行操作
    for _ in 0..1000 {
        let _data = vec![0u8; 1024 * 1024]; // 1MB
    }
    
    // 获取最终内存
    let final_memory = get_memory_usage();
    
    // 验证内存使用 < 200MB
    assert!(final_memory - initial_memory < 200 * 1024 * 1024);
}
```

## 测试运行

### 运行所有测试

```bash
# Rust测试
cargo test

# 前端测试
cd frontend
npm run test

# E2E测试
npm run test:e2e
```

### 生成测试报告

```bash
# 代码覆盖率
cargo tarpaulin --out Html

# 前端覆盖率
npm run test:coverage
```

## 测试检查清单

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 所有E2E测试通过
- [ ] 代码覆盖率 > 80%
- [ ] 性能测试通过
- [ ] 安全测试通过
- [ ] 跨平台测试通过

## 许可证

MIT License
