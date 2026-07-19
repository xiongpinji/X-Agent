# Android应用完整实现指南

**版本**: v1.0  
**平台**: Android 10+  
**框架**: Jetpack Compose + Kotlin Coroutines

---

## 项目结构

```
android/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/xagent/
│   │   │   │   ├── XAgentApp.kt
│   │   │   │   ├── MainActivity.kt
│   │   │   │   ├── features/
│   │   │   │   │   ├── auth/
│   │   │   │   │   │   ├── BiometricAuthScreen.kt
│   │   │   │   │   │   ├── LoginScreen.kt
│   │   │   │   │   │   └── AuthViewModel.kt
│   │   │   │   │   ├── tasks/
│   │   │   │   │   │   ├── TaskListScreen.kt
│   │   │   │   │   │   ├── TaskDetailScreen.kt
│   │   │   │   │   │   └── TaskViewModel.kt
│   │   │   │   │   ├── workflows/
│   │   │   │   │   │   ├── WorkflowListScreen.kt
│   │   │   │   │   │   ├── WorkflowExecutionScreen.kt
│   │   │   │   │   │   └── WorkflowViewModel.kt
│   │   │   │   │   └── settings/
│   │   │   │   │       ├── SettingsScreen.kt
│   │   │   │   │       └── SettingsViewModel.kt
│   │   │   │   ├── services/
│   │   │   │   │   ├── ApiService.kt
│   │   │   │   │   ├── BiometricService.kt
│   │   │   │   │   ├── NotificationService.kt
│   │   │   │   │   ├── SyncService.kt
│   │   │   │   │   └── StorageService.kt
│   │   │   │   ├── models/
│   │   │   │   │   ├── Task.kt
│   │   │   │   │   ├── Workflow.kt
│   │   │   │   │   └── User.kt
│   │   │   │   ├── utils/
│   │   │   │   │   ├── Constants.kt
│   │   │   │   │   ├── Extensions.kt
│   │   │   │   │   └── Helpers.kt
│   │   │   │   └── di/
│   │   │   │       └── AppModule.kt
│   │   │   ├── res/
│   │   │   │   ├── values/
│   │   │   │   ├── drawable/
│   │   │   │   └── mipmap/
│   │   │   └── AndroidManifest.xml
│   │   └── test/
│   │       └── java/com/xagent/
│   └── build.gradle.kts
└── gradle/
    └── wrapper/
```

---

## 核心功能实现

### 1. 生物识别认证

```kotlin
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import java.util.concurrent.Executor

class BiometricService(private val activity: FragmentActivity) {
  private lateinit var executor: Executor
  private lateinit var biometricPrompt: BiometricPrompt
  private lateinit var promptInfo: BiometricPrompt.PromptInfo
  
  init {
    setupBiometric()
  }
  
  private fun setupBiometric() {
    executor = ContextCompat.getMainExecutor(activity)
    
    biometricPrompt = BiometricPrompt(activity, executor,
      object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
          super.onAuthenticationSucceeded(result)
          handleAuthenticationSuccess()
        }
        
        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
          super.onAuthenticationError(errorCode, errString)
          handleAuthenticationError(errString.toString())
        }
        
        override fun onAuthenticationFailed() {
          super.onAuthenticationFailed()
          handleAuthenticationFailed()
        }
      })
    
    promptInfo = BiometricPrompt.PromptInfo.Builder()
      .setTitle("生物识别认证")
      .setSubtitle("使用指纹或面部识别登录")
      .setNegativeButtonText("取消")
      .build()
  }
  
  fun authenticate() {
    biometricPrompt.authenticate(promptInfo)
  }
  
  private fun handleAuthenticationSuccess() {
    // 保存认证令牌
    val token = "auth_token_here"
    EncryptedSharedPreferences.saveToken(token)
  }
  
  private fun handleAuthenticationError(error: String) {
    // 处理认证错误
    println("Authentication error: $error")
  }
  
  private fun handleAuthenticationFailed() {
    // 处理认证失败
    println("Authentication failed")
  }
}
```

### 2. FCM推送通知

```kotlin
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class XAgentMessagingService : FirebaseMessagingService() {
  override fun onMessageReceived(remoteMessage: RemoteMessage) {
    super.onMessageReceived(remoteMessage)
    
    val title = remoteMessage.notification?.title ?: "X-Agent"
    val body = remoteMessage.notification?.body ?: ""
    val data = remoteMessage.data
    
    sendNotification(title, body, data)
  }
  
  override fun onNewToken(token: String) {
    super.onNewToken(token)
    // 将token发送到服务器
    sendTokenToServer(token)
  }
  
  private fun sendNotification(title: String, body: String, data: Map<String, String>) {
    val notificationId = System.currentTimeMillis().toInt()
    
    val notification = NotificationCompat.Builder(this, CHANNEL_ID)
      .setSmallIcon(R.drawable.ic_notification)
      .setContentTitle(title)
      .setContentText(body)
      .setAutoCancel(true)
      .setContentIntent(createPendingIntent(data))
      .build()
    
    NotificationManagerCompat.from(this).notify(notificationId, notification)
  }
  
  private fun createPendingIntent(data: Map<String, String>): PendingIntent {
    val intent = Intent(this, MainActivity::class.java).apply {
      flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
      putExtras(data.toBundle())
    }
    
    return PendingIntent.getActivity(
      this, 0, intent,
      PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
    )
  }
  
  private fun sendTokenToServer(token: String) {
    // 实现发送token到服务器的逻辑
  }
  
  companion object {
    private const val CHANNEL_ID = "xagent_notifications"
  }
}
```

### 3. Google Drive同步

```kotlin
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.api.client.googleapis.extensions.android.gms.auth.GoogleAccountCredential
import com.google.api.services.drive.Drive
import com.google.api.services.drive.DriveScopes
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class GoogleDriveSyncService(private val context: Context) {
  private lateinit var googleSignInClient: GoogleSignInClient
  private var driveService: Drive? = null
  
  init {
    setupGoogleSignIn()
  }
  
  private fun setupGoogleSignIn() {
    val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
      .requestScopes(Scope(DriveScopes.DRIVE_APPFOLDER))
      .build()
    
    googleSignInClient = GoogleSignIn.getClient(context, gso)
  }
  
  suspend fun syncData() = withContext(Dispatchers.IO) {
    try {
      val account = GoogleSignIn.getLastSignedInAccount(context)
      if (account != null) {
        val credential = GoogleAccountCredential.usingOAuth2(
          context,
          listOf(DriveScopes.DRIVE_APPFOLDER)
        )
        credential.selectedAccount = account.account
        
        driveService = Drive.Builder(
          com.google.api.client.http.javanet.NetHttpTransport(),
          com.google.api.client.json.jackson2.JacksonFactory.getDefaultInstance(),
          credential
        ).setApplicationName("X-Agent").build()
        
        uploadData()
      }
    } catch (e: Exception) {
      e.printStackTrace()
    }
  }
  
  private suspend fun uploadData() = withContext(Dispatchers.IO) {
    try {
      val fileMetadata = com.google.api.services.drive.model.File()
      fileMetadata.name = "xagent_data.json"
      fileMetadata.parents = listOf("appDataFolder")
      
      val fileContent = java.io.FileContent("application/json", java.io.File("data.json"))
      
      driveService?.files()?.create(fileMetadata, fileContent)
        ?.setFields("id")
        ?.execute()
    } catch (e: Exception) {
      e.printStackTrace()
    }
  }
}
```

### 4. 离线存储

```kotlin
import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "tasks")
data class TaskEntity(
  @PrimaryKey val id: String,
  val title: String,
  val description: String,
  val status: String,
  val createdAt: Long,
  val updatedAt: Long
)

@Dao
interface TaskDao {
  @Query("SELECT * FROM tasks")
  fun getAllTasks(): Flow<List<TaskEntity>>
  
  @Query("SELECT * FROM tasks WHERE id = :id")
  suspend fun getTaskById(id: String): TaskEntity?
  
  @Insert(onConflict = OnConflictStrategy.REPLACE)
  suspend fun insertTask(task: TaskEntity)
  
  @Update
  suspend fun updateTask(task: TaskEntity)
  
  @Delete
  suspend fun deleteTask(task: TaskEntity)
}

@Database(entities = [TaskEntity::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
  abstract fun taskDao(): TaskDao
  
  companion object {
    @Volatile
    private var INSTANCE: AppDatabase? = null
    
    fun getInstance(context: Context): AppDatabase {
      return INSTANCE ?: synchronized(this) {
        Room.databaseBuilder(
          context.applicationContext,
          AppDatabase::class.java,
          "xagent_db"
        ).build().also { INSTANCE = it }
      }
    }
  }
}
```

---

## UI实现

### 1. 主应用

```kotlin
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

@Composable
fun XAgentApp() {
  val navController = rememberNavController()
  
  Scaffold { paddingValues ->
    NavHost(
      navController = navController,
      startDestination = "login",
      modifier = Modifier.padding(paddingValues)
    ) {
      composable("login") {
        LoginScreen(navController)
      }
      composable("tasks") {
        TaskListScreen(navController)
      }
      composable("workflows") {
        WorkflowListScreen(navController)
      }
      composable("settings") {
        SettingsScreen(navController)
      }
    }
  }
}
```

### 2. 任务列表屏幕

```kotlin
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController

@Composable
fun TaskListScreen(
  navController: NavController,
  viewModel: TaskViewModel = viewModel()
) {
  val tasks = viewModel.tasks.collectAsState(initial = emptyList())
  
  Scaffold(
    topBar = {
      TopAppBar(
        title = { Text("任务") },
        actions = {
          IconButton(onClick = { navController.navigate("new_task") }) {
            Icon(Icons.Default.Add, contentDescription = "新建任务")
          }
        }
      )
    }
  ) { paddingValues ->
    LazyColumn(
      modifier = Modifier
        .fillMaxSize()
        .padding(paddingValues)
    ) {
      items(tasks.value) { task ->
        TaskCard(
          task = task,
          onClick = { navController.navigate("task/${task.id}") }
        )
      }
    }
  }
}

@Composable
fun TaskCard(task: Task, onClick: () -> Unit) {
  Card(
    modifier = Modifier
      .fillMaxWidth()
      .padding(8.dp)
      .clickable(onClick = onClick),
    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
  ) {
    Column(modifier = Modifier.padding(16.dp)) {
      Text(task.title, style = MaterialTheme.typography.titleMedium)
      Text(task.description, style = MaterialTheme.typography.bodySmall)
      Text(task.status, style = MaterialTheme.typography.labelSmall)
    }
  }
}
```

---

## Google Play发布

### 1. 准备工作

```bash
# 1. 创建签名密钥
keytool -genkey -v -keystore xagent-release.keystore \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias xagent-key

# 2. 配置build.gradle
# 在app/build.gradle.kts中添加签名配置

# 3. 构建发布APK/AAB
./gradlew bundleRelease
```

### 2. 上传到Google Play Console

```bash
# 1. 创建应用
# 在Google Play Console中创建新应用

# 2. 填写应用信息
# - 应用名称
# - 描述
# - 分类
# - 内容分级

# 3. 上传AAB文件
# 在Release > Production中上传AAB

# 4. 设置价格和分发
# - 价格等级
# - 国家/地区
# - 发布日期

# 5. 提交审核
# 点击Review and roll out to production
```

### 3. 审核指南

- 隐私政策必须清晰说明数据收集和使用
- 生物识别认证必须有备选认证方式
- 推送通知必须可以禁用
- 不能有隐藏的功能或欺骗性内容
- 必须遵守Google Play政策

---

## 测试

### 1. 单元测试

```kotlin
import org.junit.Test
import org.junit.Before
import org.junit.runner.RunWith
import androidx.test.ext.junit.runners.AndroidJUnit4

@RunWith(AndroidJUnit4::class)
class BiometricServiceTest {
  private lateinit var service: BiometricService
  
  @Before
  fun setup() {
    // 初始化测试
  }
  
  @Test
  fun testBiometricAuthentication() {
    // 测试生物识别认证
  }
}
```

### 2. UI测试

```kotlin
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.junit.Rule

class TaskListScreenTest {
  @get:Rule
  val composeTestRule = createComposeRule()
  
  @Test
  fun testTaskListDisplay() {
    composeTestRule.setContent {
      TaskListScreen(navController = rememberNavController())
    }
    
    composeTestRule.onNodeWithText("任务").assertIsDisplayed()
  }
}
```

---

## 性能优化

- 使用`LazyColumn`处理大列表
- 避免在`Composable`中进行复杂计算
- 使用`remember`缓存计算结果
- 优化图片加载和缓存
- 使用`WorkManager`处理后台任务

---

## 依赖项

```kotlin
dependencies {
  // Jetpack Compose
  implementation("androidx.compose.ui:ui:1.5.0")
  implementation("androidx.compose.material3:material3:1.1.0")
  
  // Lifecycle
  implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.0")
  
  // Room
  implementation("androidx.room:room-runtime:2.5.2")
  kapt("androidx.room:room-compiler:2.5.2")
  
  // Biometric
  implementation("androidx.biometric:biometric:1.1.0")
  
  // Firebase
  implementation("com.google.firebase:firebase-messaging:23.2.1")
  
  // Google Play Services
  implementation("com.google.android.gms:play-services-auth:20.5.0")
  implementation("com.google.apis:google-api-services-drive:v3-rev20230519-2.0.0")
  
  // Coroutines
  implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.1")
  
  // Retrofit
  implementation("com.squareup.retrofit2:retrofit:2.9.0")
  implementation("com.squareup.retrofit2:converter-gson:2.9.0")
}
```

---

**最后更新**: 2026-05-28
