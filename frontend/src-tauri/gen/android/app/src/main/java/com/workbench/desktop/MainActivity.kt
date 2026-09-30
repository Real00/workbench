package com.workbench.desktop

import android.os.Bundle
import androidx.core.view.WindowCompat

class MainActivity : TauriActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // 工作台是内容型应用：让系统栏占位，避免刘海/状态栏压住汉堡菜单与标题。
    // （enableEdgeToEdge 时 Android WebView 常拿不到 env(safe-area-inset-*)）
    WindowCompat.setDecorFitsSystemWindows(window, true)
    super.onCreate(savedInstanceState)
  }
}
