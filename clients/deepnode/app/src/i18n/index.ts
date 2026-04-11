import { createI18n } from 'vue-i18n'

const LOCALE_KEY = 'deepnode_locale'

export const SUPPORTED_LOCALES = {
  zhCN: 'zh-CN',
  enUS: 'en-US'
} as const

type Locale = (typeof SUPPORTED_LOCALES)[keyof typeof SUPPORTED_LOCALES]

const messages = {
  'zh-CN': {
    common: {
      lang: '语言',
      chinese: '中文',
      english: 'English',
      loggedInUser: '已登录用户'
    },
    auth: {
      loginWelcome: '欢迎登录 DeepNode',
      registerWelcome: '创建 DeepNode 账号',
      loginSubtitle: '首次使用请先注册账号，登录后即可开始贡献算力。',
      registerSubtitle: '请填写完整信息，注册成功后将自动登录。',
      login: '登录',
      register: '注册',
      account: '账号',
      password: '密码',
      username: '用户名',
      phone: '手机号',
      email: '邮箱',
      accountPlaceholder: '用户名 / 手机号 / 邮箱',
      passwordPlaceholder: '请输入密码',
      usernamePlaceholder: '请输入用户名',
      phonePlaceholder: '请输入手机号',
      emailPlaceholder: '请输入邮箱',
      min8Placeholder: '至少 8 位',
      confirmPassword: '确认密码',
      confirmPasswordPlaceholder: '请再次输入密码',
      passwordMismatch: '两次输入的密码不一致',
      loginLoading: '登录中...',
      registerLoading: '注册中...',
      registerAndLogin: '注册并登录',
      fillAccountPassword: '请输入账号和密码',
      fillRegister: '请完整填写注册信息',
      badServiceResponse: '服务返回异常，请稍后重试',
      requestFailed: '请求失败',
      missingLoginData: '登录响应缺少用户信息',
      loginFailed: '登录失败',
      registerFailed: '注册失败'
    },
    device: {
      logout: '退出登录',
      switchUser: '切换用户',
      statusSuffix: '正在贡献算力',
      statusOffline: '服务未启动',
      hardwareInfo: '⚙️ 硬件信息',
      gpuModel: '显卡 / 芯片',
      modelLabel: '当前模型',
      engineLabel: '推理引擎',
      cpuUsage: 'CPU 使用率',
      gpuUsage: 'GPU 使用率',
      memUsage: '内存使用率',
      temp: '核心温度',
      uptime: '运行时长',
      avgLatency: '平均延迟',
      history: '历史记录',
      scoreLabel: '当前累计积分',
      scorePending: '积分功能即将上线',
      withdraw: '立即提现',
      realtimeTitle: '🛰 实时推理统计',
      grpcConnected: '服务运行中',
      grpcDisconnected: '服务未就绪',
      todayStats: '📊 今日统计',
      todayRequests: '今日请求数',
      todayTotalTokens: '今日 Token 总量',
      todayCompletionTokens: '今日生成 Token',
      tokenOutputRate: '输出速率',
      tokenPerSec: 'token/s',
      tokenTraffic: '🔄 Token 流量（累计）',
      inboundToken: '入站 Token（Prompt）',
      outboundToken: '出站 Token（Completion）',
      recent60s: '近 60s',
      totalStats: '📈 累计统计',
      totalRequests: '累计请求数',
      tunnelRequests: '远程任务数',
      resume: '▶ 继续运行',
      pause: '⏸ 手动暂停',
      stopService: '⏹ 停止服务',
      stopping: '正在停止...',
      smartIdleTitle: '🌙 智能休眠模式',
      smartIdleDesc: '检测到 CPU 高占用时自动暂停任务',
      safeNoticeTitle: '⚠ 安全提示：',
      safeNoticeBody:
        'DeepPool 正在受保护的沙箱环境中运行推理任务。个人文件和隐私数据不会被访问，通信已通过双向 mTLS 加密。若感知系统卡顿，请开启"智能休眠模式"。',
      blockedNoticeTitle: '🚫 安全警告：',
      blockedNoticeBody:
        '当前设备已被平台安全策略屏蔽，无法接收推理任务。可能原因：(1) 当前安装包未通过安全加固，请下载最新版本；(2) 应用文件已被篡改，请重新下载全新安装包。',
      statusBlocked: '已被屏蔽'
    },
    deviceInit: {
      title: '设备初始化',
      subtitle: '首次接入请确认加入 DeepPool 网络。',
      confirmJoin: '确认接入 DeepPool 网络',
      initializing: '初始化中...',
      progressLabel: '初始化进度：{value}%',
      simeiUnavailable: '无法获取设备唯一标识（simei）',
      localInitFailed: '本地初始化失败，请稍后重试',
      registerFailed: '设备注册失败',
      deviceNotRegistered: '平台未找到当前设备，请点击按钮完成初始化与注册。',
      modelServiceNotReady: '设备已注册，但模型服务未启动成功，请点击下方按钮重新初始化。',
      localserverStarting: '正在启动本地推理服务，请稍候...',
      localserverFailed: '本地推理服务启动失败，请尝试重启应用。',
      networkError: '网络连接异常，请检查网络后重试。',
      retryCheck: '重新检测',
      badResponse: '服务返回异常，请稍后重试',
      registeringDevice: '正在注册设备...',
      deviceRegistered: '设备注册成功，开始加载模型...',
      waitingModelLoad: '正在下载并加载模型，请稍候...',
      modelLoading: '正在加载模型: {name}',
      modelLoadFailed: '模型加载失败',
      macosUpgradeTitle: '⚠️ 强烈建议升级 macOS',
      macosUpgradeBody: '当前系统版本较低，部分最新模型（如 Gemma 4 系列）可能无法正常加载，导致推理服务异常或无法正常提供算力。强烈建议升级到 macOS 15 (Sequoia) 或更高版本，以获得完整的模型支持和最佳性能。'
    },
    settings: {
      menu: '系统设置',
      title: '系统设置',
      language: '语言设置',
      close: '关闭'
    }
  },
  'en-US': {
    common: {
      lang: 'Language',
      chinese: '中文',
      english: 'English',
      loggedInUser: 'Signed-in User'
    },
    auth: {
      loginWelcome: 'Welcome to DeepNode',
      registerWelcome: 'Create a DeepNode Account',
      loginSubtitle: 'Please register first on your first use, then sign in to start contributing compute.',
      registerSubtitle: 'Fill in all fields. You will be signed in automatically after registration.',
      login: 'Sign In',
      register: 'Sign Up',
      account: 'Account',
      password: 'Password',
      username: 'Username',
      phone: 'Phone',
      email: 'Email',
      accountPlaceholder: 'Username / Phone / Email',
      passwordPlaceholder: 'Enter password',
      usernamePlaceholder: 'Enter username',
      phonePlaceholder: 'Enter phone number',
      emailPlaceholder: 'Enter email',
      min8Placeholder: 'At least 8 characters',
      confirmPassword: 'Confirm Password',
      confirmPasswordPlaceholder: 'Re-enter your password',
      passwordMismatch: 'Passwords do not match',
      loginLoading: 'Signing in...',
      registerLoading: 'Signing up...',
      registerAndLogin: 'Sign up & Sign in',
      fillAccountPassword: 'Please enter account and password',
      fillRegister: 'Please complete all registration fields',
      badServiceResponse: 'Unexpected server response, please try again later',
      requestFailed: 'Request failed',
      missingLoginData: 'Login response missing user data',
      loginFailed: 'Login failed',
      registerFailed: 'Registration failed'
    },
    device: {
      logout: 'Sign Out',
      switchUser: 'Switch User',
      statusSuffix: 'is contributing compute',
      statusOffline: 'service not started',
      hardwareInfo: '⚙️ Hardware Info',
      gpuModel: 'GPU / Chip',
      modelLabel: 'Current Model',
      engineLabel: 'Inference Engine',
      cpuUsage: 'CPU Usage',
      gpuUsage: 'GPU Usage',
      memUsage: 'Memory Usage',
      temp: 'Core Temp',
      uptime: 'Uptime',
      avgLatency: 'Avg Latency',
      history: 'History',
      scoreLabel: 'Current Total Points',
      scorePending: 'Points feature coming soon',
      withdraw: 'Withdraw Now',
      realtimeTitle: '🛰 Realtime Inference Stats',
      grpcConnected: 'Service Running',
      grpcDisconnected: 'Service Not Ready',
      todayStats: '📊 Today',
      todayRequests: 'Today Requests',
      todayTotalTokens: 'Today Total Tokens',
      todayCompletionTokens: 'Today Completion Tokens',
      tokenOutputRate: 'Output Rate',
      tokenPerSec: 'token/s',
      tokenTraffic: '🔄 Token Traffic (Cumulative)',
      inboundToken: 'Inbound Tokens (Prompt)',
      outboundToken: 'Outbound Tokens (Completion)',
      recent60s: 'Last 60s',
      totalStats: '📈 Cumulative',
      totalRequests: 'Total Requests',
      tunnelRequests: 'Remote Tasks',
      resume: '▶ Resume',
      pause: '⏸ Pause',
      stopService: '⏹ Stop Service',
      stopping: 'Stopping...',
      smartIdleTitle: '🌙 Smart Idle Mode',
      smartIdleDesc: 'Automatically pause tasks when high CPU usage is detected',
      safeNoticeTitle: '⚠ Security Notice:',
      safeNoticeBody:
        'DeepPool runs inference tasks in a protected sandbox. Personal files and private data are not accessed, and communication is secured with mutual mTLS. Enable Smart Idle Mode if your system feels sluggish.',
      blockedNoticeTitle: '🚫 Security Warning:',
      blockedNoticeBody:
        'This device has been blocked by the platform security policy and cannot receive inference tasks. Possible causes: (1) this installation package lacks security hardening — please download the latest version; (2) application files have been tampered with — please re-download a fresh installation package.',
      statusBlocked: 'Blocked'
    },
    deviceInit: {
      title: 'Device Initialization',
      subtitle: 'Please confirm to join the DeepPool network for first-time access.',
      confirmJoin: 'Confirm to Join DeepPool Network',
      initializing: 'Initializing...',
      progressLabel: 'Initialization Progress: {value}%',
      simeiUnavailable: 'Unable to obtain device simei',
      localInitFailed: 'Local initialization failed, please try again later',
      registerFailed: 'Device registration failed',
      deviceNotRegistered: 'This device is not registered on platform. Click the button to initialize and register it.',
      modelServiceNotReady: 'Device exists, but model service did not start successfully. Click the button below to re-initialize.',
      localserverStarting: 'Starting local inference service, please wait...',
      localserverFailed: 'Local inference service failed to start. Please restart the application.',
      networkError: 'Network connection error. Please check your network and try again.',
      retryCheck: 'Retry',
      badResponse: 'Unexpected server response, please try again later',
      registeringDevice: 'Registering device...',
      deviceRegistered: 'Device registered, loading model...',
      waitingModelLoad: 'Downloading and loading model, please wait...',
      modelLoading: 'Loading model: {name}',
      modelLoadFailed: 'Model loading failed',
      macosUpgradeTitle: '⚠️ macOS Upgrade Strongly Recommended',
      macosUpgradeBody: 'Your current macOS version is outdated. Some latest models (e.g. Gemma 4 series) may fail to load properly, causing inference errors or inability to provide compute. We strongly recommend upgrading to macOS 15 (Sequoia) or later for full model support and best performance.'
    },
    settings: {
      menu: 'Settings',
      title: 'System Settings',
      language: 'Language',
      close: 'Close'
    }
  }
} as const

function resolveInitialLocale(): Locale {
  const cached = localStorage.getItem(LOCALE_KEY)
  if (cached === SUPPORTED_LOCALES.zhCN || cached === SUPPORTED_LOCALES.enUS) {
    return cached
  }
  const navLang = (navigator.language || '').toLowerCase()
  return navLang.startsWith('zh') ? SUPPORTED_LOCALES.zhCN : SUPPORTED_LOCALES.enUS
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: SUPPORTED_LOCALES.enUS,
  messages
})

export { LOCALE_KEY }
