#!/usr/bin/env python
"""验证模板格式"""
import os, sys, django

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from languages.models import CardTemplate

zh = CardTemplate.objects.get(language__code='zh')

print('=== Card 1 Back 格式检查 ===')
has_standalone_hr = '<hr id="answer">' in zh.back_template
has_answer_title = 'TitleBar title-r' in zh.back_template
has_integrated_hr = 'Text_Card radius"><hr id=answer>' in zh.back_template

print(f'✓ 没有独立 hr 标签' if not has_standalone_hr else '❌ 仍有独立 hr 标签')
print(f'✓ 没有 Answer 标题' if not has_answer_title else '❌ 仍有 Answer 标题')
print(f'✓ hr 在 Text_Card 内部' if has_integrated_hr else '❌ hr 不在 Text_Card 内部')

print('\n=== Card 2 Back 格式检查 ===')
has_standalone_hr2 = '<hr id="answer">' in zh.back_template_card2
has_answer_title2 = 'TitleBar title-r' in zh.back_template_card2
has_integrated_hr2 = 'Text_Card radius"><hr id=answer>' in zh.back_template_card2

print(f'✓ 没有独立 hr 标签' if not has_standalone_hr2 else '❌ 仍有独立 hr 标签')
print(f'✓ 没有 Answer 标题' if not has_answer_title2 else '❌ 仍有 Answer 标题')
print(f'✓ hr 在 Text_Card 内部' if has_integrated_hr2 else '❌ hr 不在 Text_Card 内部')

print('\n=== 例句格式检查 ===')
has_inline_audio1 = 'exemple-ZH}}{{exemple1-Audio}}' in zh.back_template
has_inline_audio2 = 'exemple-ZH}}{{exemple1-Audio}}' in zh.back_template_card2

print(f'✓ Card 1 音频在同一行' if has_inline_audio1 else '❌ Card 1 音频不在同一行')
print(f'✓ Card 2 音频在同一行' if has_inline_audio2 else '❌ Card 2 音频不在同一行')

print('\n所有测试:', '✅ 通过' if all([
    not has_standalone_hr, not has_answer_title, has_integrated_hr,
    not has_standalone_hr2, not has_answer_title2, has_integrated_hr2,
    has_inline_audio1, has_inline_audio2
]) else '❌ 失败')
