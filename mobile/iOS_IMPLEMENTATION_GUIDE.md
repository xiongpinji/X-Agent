# iOS应用完整实现指南

**版本**: v1.0  
**平台**: iOS 14+  
**框架**: SwiftUI + Combine

---

## 项目结构

```
ios/
├── XAgent/
│   ├── App/
│   │   ├── XAgentApp.swift
│   │   └── AppDelegate.swift
│   ├── Features/
│   │   ├── Auth/
│   │   │   ├── BiometricAuthView.swift
│   │   │   ├── LoginView.swift
│   │   │   └── AuthViewModel.swift
│   │   ├── Tasks/
│   │   │   ├── TaskListView.swift
│   │   │   ├── TaskDetailView.swift
│   │   │   └── TaskViewModel.swift
│   │   ├── Workflows/
│   │   │   ├── WorkflowListView.swift
│   │   │   ├── WorkflowExecutionView.swift
│   │   │   └── WorkflowViewModel.swift
│   │   └── Settings/
│   │       ├── SettingsView.swift
│   │       └── SettingsViewModel.swift
│   ├── Services/
│   │   ├── APIService.swift
│   │   ├── BiometricService.swift
│   │   ├── NotificationService.swift
│   │   ├── SyncService.swift
│   │   └── StorageService.swift
│   ├── Models/
│   │   ├── Task.swift
│   │   ├── Workflow.swift
│   │   └── User.swift
│   ├── Utils/
│   │   ├── Constants.swift
│   │   ├── Extensions.swift
│   │   └── Helpers.swift
│   └── Resources/
│       ├── Assets.xcassets
│       ├── Localizable.strings
│       └── Info.plist
└── XAgentTests/
    ├── AuthTests.swift
    ├── TaskTests.swift
    └── SyncTests.swift
```

---

## 核心功能实现

### 1. 生物识别认证

```swift
import LocalAuthentication

class BiometricService: NSObject, ObservableObject {
  @Published var isAuthenticated = false
  @Published var error: String?
  
  private let context = LAContext()
  
  func authenticate() {
    var error: NSError?
    
    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
      self.error = error?.localizedDescription ?? "生物识别不可用"
      return
    }
    
    let reason = "使用Face ID或Touch ID登录X-Agent"
    
    context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { [weak self] success, error in
      DispatchQueue.main.async {
        if success {
          self?.isAuthenticated = true
          self?.saveAuthToken()
        } else {
          self?.error = error?.localizedDescription ?? "认证失败"
        }
      }
    }
  }
  
  func isBiometricAvailable() -> Bool {
    var error: NSError?
    return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
  }
  
  func getBiometricType() -> String {
    if #available(iOS 14.0, *) {
      switch context.biometryType {
      case .faceID:
        return "Face ID"
      case .touchID:
        return "Touch ID"
      case .none:
        return "None"
      @unknown default:
        return "Unknown"
      }
    }
    return "Touch ID"
  }
  
  private func saveAuthToken() {
    // 保存到Keychain
    let token = "auth_token_here"
    KeychainService.save(token, forKey: "authToken")
  }
}
```

### 2. 推送通知

```swift
import UserNotifications

class NotificationService: NSObject, UNUserNotificationCenterDelegate {
  static let shared = NotificationService()
  
  func requestAuthorization() {
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
      if granted {
        DispatchQueue.main.async {
          UIApplication.shared.registerForRemoteNotifications()
        }
      }
    }
  }
  
  func handleRemoteNotification(_ userInfo: [AnyHashable: Any]) {
    if let taskId = userInfo["taskId"] as? String {
      // 处理任务更新通知
      NotificationCenter.default.post(name: NSNotification.Name("TaskUpdated"), object: taskId)
    }
  }
  
  func sendLocalNotification(title: String, body: String, delay: TimeInterval = 5) {
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    content.sound = .default
    content.badge = NSNumber(value: UIApplication.shared.applicationIconBadgeNumber + 1)
    
    let trigger = UNTimeIntervalNotificationTrigger(timeInterval: delay, repeats: false)
    let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
    
    UNUserNotificationCenter.current().add(request) { error in
      if let error = error {
        print("Failed to schedule notification: \(error)")
      }
    }
  }
}
```

### 3. iCloud同步

```swift
import CloudKit

class CloudSyncService: NSObject, ObservableObject {
  @Published var isSyncing = false
  @Published var lastSyncDate: Date?
  
  private let container = CKContainer.default()
  private let database: CKDatabase
  
  override init() {
    self.database = container.privateCloudDatabase
    super.init()
  }
  
  func syncTasks() {
    isSyncing = true
    
    let predicate = NSPredicate(value: true)
    let query = CKQuery(recordType: "Task", predicate: predicate)
    
    database.perform(query, inZoneWith: nil) { [weak self] records, error in
      DispatchQueue.main.async {
        self?.isSyncing = false
        
        if let error = error {
          print("Sync error: \(error)")
          return
        }
        
        if let records = records {
          self?.processSyncedRecords(records)
          self?.lastSyncDate = Date()
        }
      }
    }
  }
  
  func uploadTask(_ task: Task) {
    let record = CKRecord(recordType: "Task")
    record["title"] = task.title
    record["description"] = task.description
    record["status"] = task.status
    record["updatedAt"] = Date()
    
    database.save(record) { _, error in
      if let error = error {
        print("Upload error: \(error)")
      }
    }
  }
  
  private func processSyncedRecords(_ records: [CKRecord]) {
    // 处理同步的记录
    for record in records {
      if let title = record["title"] as? String {
        print("Synced task: \(title)")
      }
    }
  }
}
```

### 4. 离线存储

```swift
import CoreData

class StorageService: NSObject, ObservableObject {
  static let shared = StorageService()
  
  let persistentContainer: NSPersistentContainer
  
  override init() {
    persistentContainer = NSPersistentContainer(name: "XAgent")
    persistentContainer.loadPersistentStores { _, error in
      if let error = error {
        print("Core Data error: \(error)")
      }
    }
    super.init()
  }
  
  func saveTask(_ task: Task) {
    let context = persistentContainer.viewContext
    let entity = NSEntityDescription.entity(forEntityName: "TaskEntity", in: context)!
    let taskEntity = NSManagedObject(entity: entity, insertInto: context)
    
    taskEntity.setValue(task.id, forKey: "id")
    taskEntity.setValue(task.title, forKey: "title")
    taskEntity.setValue(task.description, forKey: "description")
    taskEntity.setValue(task.status, forKey: "status")
    
    do {
      try context.save()
    } catch {
      print("Save error: \(error)")
    }
  }
  
  func fetchTasks() -> [Task] {
    let context = persistentContainer.viewContext
    let request = NSFetchRequest<NSManagedObject>(entityName: "TaskEntity")
    
    do {
      let results = try context.fetch(request)
      return results.compactMap { entity in
        Task(
          id: entity.value(forKey: "id") as? String ?? "",
          title: entity.value(forKey: "title") as? String ?? "",
          description: entity.value(forKey: "description") as? String ?? "",
          status: entity.value(forKey: "status") as? String ?? ""
        )
      }
    } catch {
      print("Fetch error: \(error)")
      return []
    }
  }
}
```

---

## UI实现

### 1. 主应用视图

```swift
import SwiftUI

@main
struct XAgentApp: App {
  @StateObject private var authService = BiometricService()
  @StateObject private var notificationService = NotificationService()
  
  var body: some Scene {
    WindowGroup {
      if authService.isAuthenticated {
        MainTabView()
      } else {
        LoginView(authService: authService)
      }
    }
  }
}
```

### 2. 任务列表视图

```swift
struct TaskListView: View {
  @StateObject private var viewModel = TaskViewModel()
  @State private var showNewTaskSheet = false
  
  var body: some View {
    NavigationView {
      List {
        ForEach(viewModel.tasks) { task in
          NavigationLink(destination: TaskDetailView(task: task)) {
            TaskRowView(task: task)
          }
        }
      }
      .navigationTitle("任务")
      .toolbar {
        ToolbarItem(placement: .navigationBarTrailing) {
          Button(action: { showNewTaskSheet = true }) {
            Image(systemName: "plus")
          }
        }
      }
      .sheet(isPresented: $showNewTaskSheet) {
        NewTaskView(viewModel: viewModel)
      }
      .onAppear {
        viewModel.fetchTasks()
      }
    }
  }
}
```

---

## App Store发布

### 1. 准备工作

```bash
# 1. 创建App ID
# 在Apple Developer Portal中创建App ID

# 2. 创建证书
# 生成Certificate Signing Request (CSR)
# 在Apple Developer Portal中创建iOS Distribution Certificate

# 3. 创建配置文件
# 创建App Store配置文件

# 4. 配置Xcode
# 在Xcode中配置Team ID和Bundle ID
```

### 2. 构建和提交

```bash
# 1. 更新版本号
# 在Xcode中更新Version和Build Number

# 2. 构建应用
# Product > Archive

# 3. 上传到App Store Connect
# 在Organizer中选择Archive，点击Upload to App Store

# 4. 填写应用信息
# - 应用名称
# - 描述
# - 关键词
# - 支持URL
# - 隐私政策URL

# 5. 设置价格和可用性
# - 价格等级
# - 发布日期
# - 地区

# 6. 提交审核
# 点击Submit for Review
```

### 3. 审核指南

- 隐私政策必须清晰说明数据收集和使用
- 生物识别认证必须有备选认证方式
- 推送通知必须可以禁用
- 不能有隐藏的功能或欺骗性内容

---

## 测试

### 1. 单元测试

```swift
import XCTest

class BiometricServiceTests: XCTestCase {
  var service: BiometricService!
  
  override func setUp() {
    super.setUp()
    service = BiometricService()
  }
  
  func testBiometricAvailability() {
    let available = service.isBiometricAvailable()
    XCTAssertTrue(available)
  }
  
  func testBiometricType() {
    let type = service.getBiometricType()
    XCTAssertNotNil(type)
  }
}
```

### 2. UI测试

```swift
import XCTest

class TaskListUITests: XCTestCase {
  func testTaskListDisplay() {
    let app = XCUIApplication()
    app.launch()
    
    let taskList = app.tables["taskList"]
    XCTAssertTrue(taskList.exists)
  }
}
```

---

## 性能优化

- 使用`@StateObject`管理状态
- 避免在`body`中进行复杂计算
- 使用`LazyVStack`处理大列表
- 优化图片加载和缓存

---

**最后更新**: 2026-05-28
