from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Release83FullMenuUxTests(unittest.TestCase):
    def test_backup_status_is_concise_and_staged(self):
        text=(ROOT/"bin"/"vfops-auto-backup").read_text(encoding="utf-8")
        status=re.search(r"\nshow_status\(\) \{\n(?P<body>.*?)\n\}\n\nenable_or_update\(\)",text,re.S)
        self.assertIsNotNone(status)
        body=status.group("body")
        for label in ("结论        ","自动备份    ","网站        ","Google      ","B2          ","本地保留    ","下一步      "):
            self.assertIn(label,body)
        self.assertNotIn("配置结构：",body)
        self.assertNotIn("上次各网站：",body)
        self.assertIn("首次验证：先备份一个网站",body)
        self.assertIn("继续验证：备份全部网站",body)

    def test_initialization_hides_engineering_tuning_values(self):
        text=(ROOT/"bin"/"vfops-init-ui").read_text(encoding="utf-8")
        block=text[text.index("resource_profile_for_init() {"):text.index("\nfinal_init_verify()",text.index("resource_profile_for_init() {"))]
        self.assertIn("性能配置建议已生成",block)
        self.assertIn("当前不适合自动调整",block)
        self.assertIn("性能配置已应用并验证",block)
        self.assertNotIn("MySQL缓冲池",block)
        self.assertNotIn("PHP热点上限",block)
        self.assertNotIn("已识别资源方案：",block)
        self.assertNotIn('ui_note "$changes"',block)

    def test_migration_hides_internal_task_id_from_ordinary_pages(self):
        text=(ROOT/"bin"/"vfops-migrate-ui").read_text(encoding="utf-8")
        self.assertNotIn("迁移任务编号：",text)
        self.assertNotIn('ui_flow "迁移任务：$mid"',text)
        self.assertIn("旧服务器 %s · ",text)
        self.assertIn("迁移任务状态",text)

    def test_website_menu_remains_flat(self):
        text=(ROOT/"bin"/"vfops-user").read_text(encoding="utf-8")
        self.assertNotIn("backup_menu()",text)
        for label in ("立即备份一个网站","从备份恢复网站","自动备份与异地备份","服务器迁移"):
            self.assertIn(label,text)


if __name__=="__main__":
    unittest.main()
