# 余额桌宠 · 安卓版

把 [VK-1（DSH 余额桌宠）](https://github.com/VKmich16/VK-1) 搬到安卓上的**非官方移植**：
一个浮在所有 App 上面的透明悬浮窗，角色举着平板实时显示 DeepSeek 余额。

> 已获原作者 [@VKmich16](https://github.com/VKmich16) 知情同意。上游为 MIT 协议，见 [LICENSE](LICENSE)。

<p align="center">
  <img src="docs/icon.png" width="128" alt="图标">
</p>

## 它是什么

余额每 10 秒拉一次。**扣费 0.01 元** → 她红闪 + 震动 + 头顶飘出 `-0.01`；
**充值** → 屏幕边掉下一盆米饭，拖到她身上才入账，吃完掉一个铁盆，铁盆能扣在她头上；
**头上已经有盆时**，新掉下来的米饭会撞在盆底「铛」一声弹开，弹到地上还能再捡起来喂。

表情、抚摸、火控雷达名牌、峰谷时钟、今日消费、分路音效，都按桌面版的行为保留。

## 安装

1. 下载 [`dist/vk1-pet-1.4.4.apk`](dist/vk1-pet-1.4.4.apk)
2. 安装（Android 8.0+，需要允许「安装未知来源应用」）
3. 打开 App：填 `sk-` 开头的 DeepSeek API Key（**可以跳过**，跳过时平板显示「未连接」）
4. 点「授权悬浮窗」→ 允许「显示在其他应用上层」→ 点「启动桌宠」，回桌面

Key 只存在本机 `SharedPreferences`，只会发往 `api.deepseek.com`，不上传、不写日志。

## 手势

| 操作 | 效果 |
| --- | --- |
| 单指在她身上划 | 摸头 |
| **两指拖动** | 搬动整个挂件（松手自动吸边） |
| 长按她 0.56 秒 / 点右上角「⋯」 | 菜单（设置 / 演示 / 刷新余额 / 峰谷时钟） |
| 单指拖米饭盆、铁盆 | 拖动道具；拖到她身上喂饭，铁盆拖到头顶会扣上 |
| 双击她的头 | 打掉头上的铁盆 |
| 头上有盆时扔米饭 | 撞在盆底弹开（按落地速度决定弹多高、飞多远），弹到地上照常能喂 |
| 点平板 | 切换峰谷时钟 |

## 实现方式

没有重写渲染，而是**把上游的网页版挂件塞进一个 WebView**，外面套一层安卓悬浮窗外壳：

- **渲染层**：满屏透明 WebView，`FLAG_NOT_TOUCHABLE`，不接收触摸，所以盆能从屏幕顶端掉下来、能拖到任何角落；
- **触摸层**：一块透明的小窗口，只覆盖「她 + 地上的道具」当前所在的矩形，把触摸转发进 WebView，其他区域的点击照常穿透给下面的 App；
- **原生层**：余额轮询、震动、通知、Key 存储，通过 `@JavascriptInterface` 喂给页面；
- `widget.js` 是上游文件 + 40 处定点补丁（`tools/patch_widget.py`），补丁逐条带注释。

## 已知限制

- **平时看起来是 80% 不透明**：MIUI 会给所有 `FLAG_NOT_TOUCHABLE` 的悬浮窗整体压 20% 透明。
  满屏渲染必须用不可点的窗口，否则会吞掉全屏触摸，所以这条暂时无解。
  对照实验：同样 alpha=1 的可点窗口是纯色的，不可点的就是 0.8。
- 透明区域里「她 + 道具」的矩形会吃掉触摸（这是单窗口方案的物理上限）。
- 图标是手写的 `resources.arsc`（没走 aapt）。两条硬要求写在 `tools/arsc.py` 里：字符串池必须
  UTF-16、`resources.arsc` 必须 STORED + 4 字节对齐，否则安装器会报 `-124`。

## 目录

```
app/src/com/vk1/pet/   安卓外壳：悬浮窗服务、余额轮询、JS 桥、崩溃日志
app/src/assets/vk1/    网页版挂件（widget.js 由 tools/patch_widget.py 生成）
tools/                 axml.py 写 AndroidManifest、arsc.py 写资源表、构建与校验小工具
vendor/widget.js       上游原始文件（打补丁的输入）
res/icon.png           512×512 图标
dist/                  打好的 APK
```

## 自己编译

需要 JDK 17+ 和三个依赖（**不入库**，体积大且 android.jar 的分发另有条款）：

```
deps/android.jar          # Android SDK platform 35 的 android.jar
deps/r8-8.13.25.jar       # d8，class → dex
deps/apksig-8.13.2.jar    # v1+v2+v3 签名
```

然后：

```sh
python3 build.py            # 产物 build/vk1-pet.apk
```

首次构建会生成 `build/debug.p12`（自签名密钥）。**升级要用同一个密钥**，别删。

改网页部分后需要重新打补丁：

```sh
python3 tools/patch_widget.py
```

## 更新日志

- **1.4.4** —— 首页加「扣费时震动」开关（默认开）。关掉后扣费只有红闪和 `-0.01` 飘字，不再震。
- **1.4.3** —— 铁盆挡饭：头上已经戴着盆时，落下的米饭会撞在盆底弹开，弹力按落地速度算
  （越高掉得越远），并且**碰过盆的米饭必须先落地**才可能被喂进去——不然它会从盆沿滑下来
  正好扫过脸，被当成吃掉了，然后连锁掉出新的盆。顺带补了高速下落时穿透判定带的问题（扫掠检测）。
- **1.3.4** —— 第一个公开版本：图标改成角色本人、`resources.arsc` 走 UTF-16 + STORED 对齐、
  不透明度滑杆、没填 Key 时显示「未连接」。

## 致谢

- [VKmich16/VK-1](https://github.com/VKmich16/VK-1) —— 原作：美术、音效、全部原始行为
- [YCTS-otree/VK-1](https://github.com/YCTS-otree/VK-1) —— 网页版挂件（本项目的渲染基础）

均为 MIT，版权声明见 [LICENSE](LICENSE)。
