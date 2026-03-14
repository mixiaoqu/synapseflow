"""
测试需求提取节点
"""
import asyncio
import json
from app.agents.nodes.prototype import extract_requirements_node


async def test_extract_simple():
    """测试简单需求文档"""
    print("\n" + "="*60)
    print("测试1：简单需求文档")
    print("="*60)
    
    state = {
        "requirements_doc": """
创建一个简单的登录页面，包含：
- 用户名输入框
- 密码输入框
- 登录按钮
- "忘记密码"链接

风格要现代简约，蓝色系。
        """,
        "extracted_requirements": {},
        "ui_components": [],
        "design_system": {},
        "generated_html": "",
        "validation_errors": [],
        "preview_url": "",
        "is_valid": False,
        "metadata": {}
    }
    
    result = await extract_requirements_node(state)
    extracted = result["extracted_requirements"]
    
    print("\n[OK] 提取结果：")
    print(json.dumps(extracted, ensure_ascii=False, indent=2))
    
    # 验证关键字段
    assert "page_info" in extracted, "缺少page_info"
    assert "functional_modules" in extracted, "缺少functional_modules"
    assert "visual_style" in extracted, "缺少visual_style"
    
    print("\n[OK] 所有必需字段都存在")


async def test_extract_complex():
    """测试复杂需求文档"""
    print("\n" + "="*60)
    print("测试2：复杂产品落地页")
    print("="*60)
    
    state = {
        "requirements_doc": """
# 产品落地页需求

## 页面结构
1. 顶部导航栏
   - Logo（左侧）
   - 菜单：首页、产品、定价、关于我们
   - "立即开始"按钮（右侧，蓝色）

2. Hero区域
   - 主标题："让AI赋能你的团队"
   - 副标题："下一代智能协作平台，提升10倍效率"
   - 两个CTA按钮：
     - "免费试用"（蓝色，主要）
     - "观看演示"（白色，次要）
   - 背景：渐变色（蓝紫色）

3. 产品特性（三栏）
   - 特性1：智能协作
     - 图标：💡
     - 描述：实时同步团队工作
   - 特性2：自动化工作流
     - 图标：⚡
     - 描述：减少重复劳动
   - 特性3：企业级安全
     - 图标：🔒
     - 描述：数据加密存储

4. 底部联系表单
   - 字段：姓名（必填）、邮箱（必填）、消息（选填）
   - 提交按钮
   - 提交后显示成功提示

## 设计要求
- 现代简约风格
- 蓝色系主题（#3B82F6）
- 响应式布局（移动端导航菜单折叠）
- 平滑滚动动画
        """,
        "extracted_requirements": {},
        "ui_components": [],
        "design_system": {},
        "generated_html": "",
        "validation_errors": [],
        "preview_url": "",
        "is_valid": False,
        "metadata": {}
    }
    
    result = await extract_requirements_node(state)
    extracted = result["extracted_requirements"]
    
    print("\n[OK] 提取结果：")
    print(f"页面类型: {extracted['page_info']['type']}")
    print(f"功能模块数: {len(extracted.get('functional_modules', []))}")
    print(f"交互行为数: {len(extracted.get('interactions', []))}")
    print(f"数据模型数: {len(extracted.get('data_model', []))}")
    print(f"配色方案: {extracted['visual_style']['color_scheme']}")
    
    print("\n功能模块列表：")
    for module in extracted.get("functional_modules", []):
        print(f"  - {module['name']}: {module.get('description', '')}")
    
    print("\n交互行为列表：")
    for interaction in extracted.get("interactions", []):
        print(f"  - {interaction.get('trigger', '')} → {interaction.get('action', '')}")
    
    # 验证
    assert len(extracted.get("functional_modules", [])) >= 3, "应该至少识别出3个模块"
    print("\n[OK] 复杂文档解析成功")


async def test_extract_unstructured():
    """测试非结构化文档"""
    print("\n" + "="*60)
    print("测试3：非结构化纯文本")
    print("="*60)
    
    state = {
        "requirements_doc": """
我想要一个产品介绍网站，有个大大的标题写着"未来已来"，下面放三个卡片
介绍我们的优势，然后底部有个联系表单。整体要看起来很专业，用蓝色。
对了，还要有个顶部菜单，可以跳转到不同页面。
        """,
        "extracted_requirements": {},
        "ui_components": [],
        "design_system": {},
        "generated_html": "",
        "validation_errors": [],
        "preview_url": "",
        "is_valid": False,
        "metadata": {}
    }
    
    result = await extract_requirements_node(state)
    extracted = result["extracted_requirements"]
    
    print("\n[OK] 从非结构化文本中提取：")
    print(f"页面类型: {extracted['page_info']['type']}")
    print(f"功能模块: {[m['name'] for m in extracted.get('functional_modules', [])]}")
    
    assert len(extracted.get("functional_modules", [])) > 0, "应该能提取出模块"
    print("\n[OK] 非结构化文档也能正确解析")


async def main():
    """运行所有测试"""
    print("\n[TEST] 开始测试需求提取功能\n")
    
    try:
        await test_extract_simple()
        await test_extract_complex()
        await test_extract_unstructured()
        
        print("\n" + "="*60)
        print("[SUCCESS] 所有测试通过！")
        print("="*60)
    
    except Exception as e:
        print(f"\n[FAILED] 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
