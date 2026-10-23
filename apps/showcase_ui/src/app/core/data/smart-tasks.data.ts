/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

export interface AppReference {
  name: string;
  icon: string;
  pkg?: string;
  category?: string;
}

export type SuggestionCategory =
  | 'all'
  | 'flash'
  | 'pro'
  | 'cross_app'
  | 'monitor';

export interface SmartSuggestion {
  id: string;
  title: string;
  description: string;
  goal: string;
  profile: 'flash' | 'pro';
  category: 'flash' | 'pro' | 'cross_app' | 'monitor';
  tag: string;
  apps: AppReference[];
  requiredPackages?: string[];
  matchMode?: 'any' | 'all';
  priority?: number;
}

/**
 * Recognized Android App Package Registry
 */
export const APP_REGISTRY: Record<string, AppReference> = {
  // Google Suite & System
  'com.google.android.apps.maps': { name: 'Maps', icon: 'explore', pkg: 'com.google.android.apps.maps', category: 'navigation' },
  'com.google.android.gm': { name: 'Gmail', icon: 'mail', pkg: 'com.google.android.gm', category: 'productivity' },
  'com.android.chrome': { name: 'Chrome', icon: 'public', pkg: 'com.android.chrome', category: 'browser' },
  'com.google.android.youtube': { name: 'YouTube', icon: 'smart_display', pkg: 'com.google.android.youtube', category: 'entertainment' },
  'com.android.settings': { name: 'Settings', icon: 'settings', pkg: 'com.android.settings', category: 'system' },
  'com.google.android.deskclock': { name: 'Clock', icon: 'timer', pkg: 'com.google.android.deskclock', category: 'utility' },
  'com.android.deskclock': { name: 'Clock', icon: 'timer', pkg: 'com.android.deskclock', category: 'utility' },
  'com.google.android.calculator': { name: 'Calculator', icon: 'calculate', pkg: 'com.google.android.calculator', category: 'utility' },
  'com.android.calculator2': { name: 'Calculator', icon: 'calculate', pkg: 'com.android.calculator2', category: 'utility' },
  'com.google.android.apps.photos': { name: 'Photos', icon: 'photo_library', pkg: 'com.google.android.apps.photos', category: 'media' },
  'com.google.android.calendar': { name: 'Calendar', icon: 'calendar_month', pkg: 'com.google.android.calendar', category: 'productivity' },
  'com.google.android.keep': { name: 'Keep Notes', icon: 'note_alt', pkg: 'com.google.android.keep', category: 'productivity' },
  'com.android.vending': { name: 'Play Store', icon: 'storefront', pkg: 'com.android.vending', category: 'tools' },
  'com.google.android.apps.messaging': { name: 'Messages', icon: 'chat', pkg: 'com.google.android.apps.messaging', category: 'communication' },

  // Popular Ecosystem Apps
  'com.tencent.mm': { name: 'WeChat', icon: 'forum', pkg: 'com.tencent.mm', category: 'social' },
  'com.xingin.xhs': { name: 'Xiaohongshu', icon: 'auto_stories', pkg: 'com.xingin.xhs', category: 'social' },
  'com.sankuai.meituan': { name: 'Meituan', icon: 'restaurant', pkg: 'com.sankuai.meituan', category: 'lifestyle' },
  'com.dianping.v1': { name: 'Dianping', icon: 'star', pkg: 'com.dianping.v1', category: 'lifestyle' },
  'tv.danmaku.bili': { name: 'Bilibili', icon: 'video_library', pkg: 'tv.danmaku.bili', category: 'entertainment' },
  'com.eg.android.AlipayGphone': { name: 'Alipay', icon: 'account_balance_wallet', pkg: 'com.eg.android.AlipayGphone', category: 'finance' },
  'com.netease.cloudmusic': { name: 'NetEase Music', icon: 'headphones', pkg: 'com.netease.cloudmusic', category: 'entertainment' },
  'com.spotify.music': { name: 'Spotify', icon: 'music_note', pkg: 'com.spotify.music', category: 'entertainment' }
};

/**
 * Curated, clean task preset library (1~2 representative tasks per common app)
 */
export const SMART_TASK_LIBRARY: SmartSuggestion[] = [
  // 1. Google Maps
  {
    id: 'maps_coffee',
    title: '寻找精品咖啡馆',
    description: '在 Google Maps 搜索附近高评分咖啡馆',
    goal: '打开 Google Maps，搜索附近高评分的精品咖啡馆，查看排名第一的详情。',
    profile: 'flash',
    category: 'flash',
    tag: 'Maps',
    apps: [{ name: 'Maps', icon: 'explore', pkg: 'com.google.android.apps.maps' }],
    requiredPackages: ['com.google.android.apps.maps'],
    priority: 95
  },
  {
    id: 'pro_commute_share',
    title: '通勤时间预估与消息草稿',
    description: '在 Maps 查询通勤时长，在 Messages 草拟到达时间消息',
    goal: '打开 Google Maps 查询到国际机场的通勤时间并计算到达时间，然后打开 Messages 草拟一条 ETA 消息。',
    profile: 'pro',
    category: 'cross_app',
    tag: 'Maps + Messages',
    apps: [
      { name: 'Maps', icon: 'explore', pkg: 'com.google.android.apps.maps' },
      { name: 'Messages', icon: 'chat', pkg: 'com.google.android.apps.messaging' }
    ],
    requiredPackages: ['com.google.android.apps.maps', 'com.google.android.apps.messaging'],
    matchMode: 'all',
    priority: 92
  },

  // 2. Gmail
  {
    id: 'gmail_receipts',
    title: '搜索订单凭证',
    description: '在 Gmail 中查找最近的机票或快递确认邮件',
    goal: '打开 Gmail，搜索最近的机票或包裹寄递确认邮件。',
    profile: 'flash',
    category: 'flash',
    tag: 'Gmail',
    apps: [{ name: 'Gmail', icon: 'mail', pkg: 'com.google.android.gm' }],
    requiredPackages: ['com.google.android.gm'],
    priority: 90
  },
  {
    id: 'pro_email_to_calendar',
    title: '行程邮件同步到日历',
    description: '从 Gmail 提取机票或活动日期并加入 Calendar 日程',
    goal: '打开 Gmail 找到最新的活动邀请或行程，提取日期和地点，再打开 Google Calendar 创建对应日程。',
    profile: 'pro',
    category: 'cross_app',
    tag: 'Gmail + Calendar',
    apps: [
      { name: 'Gmail', icon: 'mail', pkg: 'com.google.android.gm' },
      { name: 'Calendar', icon: 'calendar_month', pkg: 'com.google.android.calendar' }
    ],
    requiredPackages: ['com.google.android.gm'],
    priority: 94
  },

  // 3. Chrome
  {
    id: 'chrome_research',
    title: '搜索 AI 突破新闻',
    description: '在 Chrome 中搜索多模态 AI 最新进展',
    goal: '打开 Chrome 浏览器，搜索多模态手机 AI Agent 的最新突破。',
    profile: 'flash',
    category: 'flash',
    tag: 'Chrome',
    apps: [{ name: 'Chrome', icon: 'public', pkg: 'com.android.chrome' }],
    requiredPackages: ['com.android.chrome'],
    priority: 88
  },
  {
    id: 'pro_research_keep',
    title: '商品调研与笔记',
    description: '在 Chrome 对比前 3 款耳机并记录到 Keep',
    goal: '打开 Chrome，调研前 3 款降噪耳机的价格与续航，并在 Keep 笔记中写一份结构化对比总结。',
    profile: 'pro',
    category: 'pro',
    tag: 'Chrome + Keep',
    apps: [
      { name: 'Chrome', icon: 'public', pkg: 'com.android.chrome' },
      { name: 'Keep Notes', icon: 'note_alt', pkg: 'com.google.android.keep' }
    ],
    requiredPackages: ['com.android.chrome'],
    priority: 91
  },

  // 4. YouTube
  {
    id: 'youtube_lofi',
    title: '播放 Lo-Fi 电台',
    description: '在 YouTube 搜索并播放 Lo-Fi 嘻哈直播流',
    goal: '打开 YouTube，搜索 “Lofi hip hop beats relaxing radio” 并点开直播流。',
    profile: 'flash',
    category: 'flash',
    tag: 'YouTube',
    apps: [{ name: 'YouTube', icon: 'smart_display', pkg: 'com.google.android.youtube' }],
    requiredPackages: ['com.google.android.youtube'],
    priority: 85
  },

  // 5. Settings
  {
    id: 'settings_display_wifi',
    title: '深色模式与 Wi-Fi 检查',
    description: '在设置中切换深色主题并检查网络连接',
    goal: '打开设置应用，进入显示设置，确认深色主题已开启，并检查 Wi-Fi 连接状态。',
    profile: 'flash',
    category: 'flash',
    tag: 'Settings',
    apps: [{ name: 'Settings', icon: 'settings', pkg: 'com.android.settings' }],
    requiredPackages: ['com.android.settings'],
    priority: 87
  },
  {
    id: 'pro_settings_qa',
    title: '子系统健康与崩溃探测',
    description: '遍历设置子菜单，验证页面加载并检查崩溃弹窗',
    goal: '探索设置子菜单（网络、已连设备、应用、电池、存储），确认每个页面无 ANR 或崩溃弹窗并汇总结果。',
    profile: 'pro',
    category: 'monitor',
    tag: 'Settings QA',
    apps: [{ name: 'Settings', icon: 'settings', pkg: 'com.android.settings' }],
    requiredPackages: ['com.android.settings'],
    priority: 93
  },

  // 6. Clock
  {
    id: 'clock_timer',
    title: '25 分钟番茄钟',
    description: '在时钟应用中开启 25 分钟专注倒计时',
    goal: '打开时钟应用，切换到计时器标签，设置 25 分钟并开始倒计时。',
    profile: 'flash',
    category: 'flash',
    tag: 'Clock',
    apps: [{ name: 'Clock', icon: 'timer', pkg: 'com.google.android.deskclock' }],
    requiredPackages: ['com.google.android.deskclock', 'com.android.deskclock'],
    priority: 86
  },

  // 7. Calculator
  {
    id: 'calc_gratuity',
    title: '分摊账单与计算小费',
    description: '用计算器计算 $186.40 的 18% 小费并由 3 人分摊',
    goal: '打开计算器，计算 $186.40 账单的 18% 小费，再除以 3 人。',
    profile: 'flash',
    category: 'flash',
    tag: 'Calculator',
    apps: [{ name: 'Calculator', icon: 'calculate', pkg: 'com.google.android.calculator' }],
    requiredPackages: ['com.google.android.calculator', 'com.android.calculator2'],
    priority: 84
  },

  // 8. Photos
  {
    id: 'photos_inspect',
    title: '查看最近截图',
    description: '打开 Google Photos 查看最新截图',
    goal: '打开 Google Photos，在截图片区查看最近的截图。',
    profile: 'flash',
    category: 'flash',
    tag: 'Photos',
    apps: [{ name: 'Photos', icon: 'photo_library', pkg: 'com.google.android.apps.photos' }],
    requiredPackages: ['com.google.android.apps.photos'],
    priority: 82
  },

  // 9. WeChat
  {
    id: 'wechat_browse',
    title: '查看微信消息',
    description: '打开微信查看最近的聊天会话',
    goal: '打开微信，查看最近的聊天消息。',
    profile: 'flash',
    category: 'flash',
    tag: 'WeChat',
    apps: [{ name: 'WeChat', icon: 'forum', pkg: 'com.tencent.mm' }],
    requiredPackages: ['com.tencent.mm'],
    priority: 89
  },
  {
    id: 'pro_wechat_to_calendar',
    title: '微信通知同步到日历',
    description: '从微信聊天提取会议通知并加入日历',
    goal: '打开微信，在置顶聊天中找到最新会议通知或活动消息，提取时间和主题，再打开 Calendar 创建日程。',
    profile: 'pro',
    category: 'cross_app',
    tag: 'WeChat + Calendar',
    apps: [
      { name: 'WeChat', icon: 'forum', pkg: 'com.tencent.mm' },
      { name: 'Calendar', icon: 'calendar_month', pkg: 'com.google.android.calendar' }
    ],
    requiredPackages: ['com.tencent.mm'],
    priority: 93
  },

  // 10. Xiaohongshu
  {
    id: 'xhs_coffee_guide',
    title: '小红书咖啡馆探店',
    description: '在小红书搜索热门精品咖啡馆点评',
    goal: '打开小红书，搜索高评分精品咖啡馆，查看第一篇笔记。',
    profile: 'flash',
    category: 'flash',
    tag: 'Xiaohongshu',
    apps: [{ name: 'Xiaohongshu', icon: 'auto_stories', pkg: 'com.xingin.xhs' }],
    requiredPackages: ['com.xingin.xhs'],
    priority: 87
  },

  // 11. Meituan / Dianping
  {
    id: 'meituan_ramen_search',
    title: '美团美食搜索',
    description: '在美团或大众点评搜索附近高评分拉面',
    goal: '打开美团或大众点评，搜索附近高评分拉面，查看排名第一的店铺评分。',
    profile: 'flash',
    category: 'flash',
    tag: 'Meituan',
    apps: [{ name: 'Meituan', icon: 'restaurant', pkg: 'com.sankuai.meituan' }],
    requiredPackages: ['com.sankuai.meituan', 'com.dianping.v1'],
    priority: 86
  },

  // 12. Bilibili
  {
    id: 'bilibili_stream',
    title: 'B站科技视频',
    description: '在 Bilibili 搜索并播放 AI Agent 教程视频',
    goal: '打开 Bilibili，搜索 “AI Agent Architecture” 并播放匹配度最高的视频。',
    profile: 'flash',
    category: 'flash',
    tag: 'Bilibili',
    apps: [{ name: 'Bilibili', icon: 'video_library', pkg: 'tv.danmaku.bili' }],
    requiredPackages: ['tv.danmaku.bili'],
    priority: 85
  },

  // 13. Play Store
  {
    id: 'pro_playstore_review',
    title: 'Play 商店应用评价研究',
    description: '在 Google Play 对比任务管理应用与评分',
    goal: '打开 Google Play，搜索高评分任务管理应用，对比前 2 名的评分与最新用户评价，并记录推荐结论。',
    profile: 'pro',
    category: 'pro',
    tag: 'Play Store',
    apps: [{ name: 'Play Store', icon: 'storefront', pkg: 'com.android.vending' }],
    requiredPackages: ['com.android.vending'],
    priority: 88
  }
];
