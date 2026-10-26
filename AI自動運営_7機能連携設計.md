# AI自動運営・7機能連携設計

対象：くらしの手帖（GitHub Pages）／便利屋まごの手INNOVATION（既存Wixサイト）

## 現在利用できるもの
- Connectors：ChatGPT側のGitHub、Wixなど、実際に接続済みのサービスを利用。
- Routine相当：ChatGPTの毎日点検タスク、GitHub Actionsの定期検証・週次記事更新。
- Dynamic Workflow相当：既存の更新・検証・公開ジョブを条件分岐させる。Claude独自機能が接続済みという意味ではない。

## Claude側の追加接続が必要なもの
- Superpowers：Claude Codeの対応するスキル／プラグインを公式配布元・導入方法・権限を確認して導入する。
- Subagents：Claude Code側で役割分担を構成する。GitHubへの書込権限は最小限にする。
- Claude in Chrome：Claude側で拡張機能の導入と明示的な接続許可が必要。
- Remote Control：Claude側の対応する遠隔操作機能を利用し、アクセス許可・利用可能プランを確認する。
- Dynamic Workflows：Claude Code側で有効な環境でのみ利用。ChatGPTの既存自動化とは区別する。

## 分担
1. サイト点検担当：公開状態、HTMLリンク、モバイル表示、問い合わせ導線を検査。
2. 記事担当：公式資料に基づく更新候補を作成。既存週次更新と二重投稿しない。
3. SEO担当：サイトマップ、検索登録、内部導線を点検。
4. 収益化担当：AdSense審査状況と提携済みA8広告のみ確認。審査結果を推測しない。
5. 統括担当：実行結果を検証し、失敗時に修正または保留を判断。

## 安全な処理順序
情報取得 → 変更候補作成 → ローカル検証 → 許可済み変更の反映 → 公開確認 → 作業引継ぎ更新。
課金、規約同意、銀行情報登録、外部アカウント認証は自動実行しない。
秘密情報をGitHub公開リポジトリに保存しない。既存のWixやGitHubの設定を上書きして壊さない。

## 未接続と完了の区別
この文書は連携設計の記録。Claudeのアカウント認証・Chrome拡張・Remote Control・Superpowers・Subagents・Claude固有Dynamic Workflowsが実際に有効になったことは意味しない。
