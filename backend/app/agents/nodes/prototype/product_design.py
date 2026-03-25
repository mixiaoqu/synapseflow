"""产品建模层：归一化规格 → 页面 / 路由 / 导航 / 用户流程，并同步 site_map 与下游兼容字段。"""
import json
import re
import time
from typing import Any, Dict, List

from loguru import logger

from app.agents.states.prototype import DocToPrototypeState
from app.core.llm import get_llm_for_planner
from app.agents.nodes.prototype.utils import parse_json_safely, normalize_requirements

# 需求正文摘录长度：用于识别文档中的模块/子模块/章节划分（与归一化规格配合）
PRODUCT_DESIGN_DOC_EXCERPT_CHARS = 8000


def _slug(text: str, fallback: str) -> str:
    raw = (text or "").strip().lower()
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "-", raw)
    t = re.sub(r"-+", "-", t).strip("-") or fallback
    return t[:64]


def _normalize_page_row(page: Dict[str, Any], idx: int) -> Dict[str, Any]:
    pid = page.get("id") or page.get("page_id")
    title = page.get("title") or page.get("name") or ("页面%s" % (idx + 1))
    if not pid:
        pid = _slug(str(title), "page-%s" % idx)
    route = page.get("route") or page.get("path") or ("#/%s" % pid)
    route = str(route)
    if not route.startswith("#") and not route.startswith("/"):
        route = "#/%s" % route.lstrip("/")
    summ = page.get("summary") or page.get("description") or ""
    if not isinstance(summ, str):
        summ = str(summ)
    ord_raw = page.get("order")
    if ord_raw is None:
        order = idx
    else:
        try:
            order = int(ord_raw)
        except (TypeError, ValueError):
            order = idx
    return {
        "id": str(pid),
        "title": str(title),
        "route": route,
        "summary": summ[:500],
        "order": order,
    }


def _dedupe_site_ids(pages: List[Dict[str, Any]]) -> None:
    seen: set = set()
    for p in pages:
        oid = p["id"]
        if oid not in seen:
            seen.add(oid)
            continue
        n = 1
        while "%s-%s" % (oid, n) in seen:
            n += 1
        nid = "%s-%s" % (oid, n)
        seen.add(nid)
        p["id"] = nid
        p["route"] = "#/%s" % nid


def _product_pages_to_site_map(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_pages = product.get("pages") or []
    rows: List[Dict[str, Any]] = []
    for i, p in enumerate(raw_pages):
        if not isinstance(p, dict):
            continue
        name = p.get("name") or p.get("title") or ("页%s" % (i + 1))
        route = p.get("route") or ""
        pid = p.get("id") or _slug(str(name), "p-%s" % i)
        row = {
            "id": str(pid),
            "title": str(name),
            "route": str(route) if route else "#/%s" % pid,
            "summary": "",
            "order": i,
        }
        mods = p.get("modules") or []
        if isinstance(mods, list) and mods:
            row["summary"] = "、".join(str(m) for m in mods[:5])[:500]
        rows.append(_normalize_page_row(row, i))
    rows.sort(key=lambda x: (x["order"], x["id"]))
    _dedupe_site_ids(rows)
    return rows


def _infer_mode(pages: List[Dict[str, Any]]) -> str:
    return "multi" if len(pages) > 1 else "single"


_NAV_TYPES = frozenset({"top", "sidebar", "tab"})


def _infer_navigation_type(
    pages: List[Dict[str, Any]],
    normalized: Dict[str, Any],
    product: Dict[str, Any],
) -> str:
    """当模型未给出合法 navigation.type 时，按页数与业务关键词推断。"""
    blob = (
        json.dumps(normalized or {}, ensure_ascii=False)
        + json.dumps(product or {}, ensure_ascii=False)
    ).lower()
    marketing = any(
        k in blob
        for k in ("官网", "落地页", "营销", "品牌", "landing page", "landing", "品牌站")
    )
    adminish = any(
        k in blob
        for k in (
            "后台",
            "管理",
            "admin",
            "仪表盘",
            "dashboard",
            "工单",
            "erp",
            "crm",
            "权限",
            "运营",
            "控制台",
        )
    )
    n = len([p for p in pages if isinstance(p, dict)])
    if n <= 1:
        if marketing:
            return "top"
        if any(k in blob for k in ("tab", "标签页", "选项卡", "页签")):
            return "tab"
        return "top"
    if n >= 3:
        return "top" if marketing else "sidebar"
    if adminish:
        return "sidebar"
    return "top"


def _coerce_nav_type(raw: Any) -> str:
    if raw is None:
        return ""
    t = str(raw).strip().lower()
    aliases = {
        "侧栏": "sidebar",
        "侧边栏": "sidebar",
        "左边栏": "sidebar",
        "左侧导航": "sidebar",
        "left": "sidebar",
        "leftnav": "sidebar",
        "标签": "tab",
        "标签页": "tab",
        "选项卡": "tab",
        "页签": "tab",
        "tabs": "tab",
        "header": "top",
        "顶栏": "top",
        "顶部": "top",
    }
    return aliases.get(t, t)


def _normalize_product_navigation(
    product: Dict[str, Any],
    normalized: Dict[str, Any],
) -> None:
    """保证 navigation.type 合法；补全 links 与页面 id 对齐。"""
    nav = product.get("navigation")
    if not isinstance(nav, dict):
        nav = {}
        product["navigation"] = nav
    t = _coerce_nav_type(nav.get("type"))
    if t not in _NAV_TYPES:
        pages = product.get("pages") or []
        t = _infer_navigation_type(
            pages if isinstance(pages, list) else [],
            normalized,
            product,
        )
    nav["type"] = t
    links = nav.get("links")
    if not isinstance(links, list):
        links = []
    pages = product.get("pages") or []
    if not links and isinstance(pages, list):
        for idx, p in enumerate(pages):
            if not isinstance(p, dict):
                continue
            label = p.get("name") or p.get("title") or ("页面%s" % (idx + 1))
            pid = p.get("id")
            if not pid:
                pid = _slug(str(label), "page-%s" % idx)
                p["id"] = str(pid)
            links.append(
                {
                    "label": str(label)[:80],
                    "target_page_id": str(pid),
                }
            )
    nav["links"] = links


def _build_legacy_extracted(
    normalized: Dict[str, Any],
    product: Dict[str, Any],
) -> Dict[str, Any]:
    """将产品层与归一化规格转为 generate/design 使用的 extracted_requirements 形状。"""
    pages = product.get("pages") or []
    first = pages[0] if pages and isinstance(pages[0], dict) else {}
    title = (
        first.get("name")
        or first.get("title")
        or (normalized.get("notes") or "原型")[:80]
        or "原型"
    )
    page_type = "landing_page"
    text_blob = json.dumps(product, ensure_ascii=False).lower()
    if any(k in text_blob for k in ["登录", "login", "注册", "signup", "表单"]):
        page_type = "form"
    elif any(k in text_blob for k in ["仪表盘", "dashboard", "统计", "看板"]):
        page_type = "dashboard"

    modules: List[Dict[str, Any]] = []
    mid = 0
    for pi, p in enumerate(pages):
        if not isinstance(p, dict):
            continue
        pname = p.get("name") or p.get("title") or ("页面%s" % (pi + 1))
        route = p.get("route") or ""
        for m in p.get("modules") or []:
            if isinstance(m, str):
                nm = m
                desc = ""
            elif isinstance(m, dict):
                nm = m.get("name") or m.get("title") or "模块"
                desc = m.get("description") or ""
            else:
                nm = str(m)
                desc = ""
            modules.append(
                {
                    "id": "mod_%s" % mid,
                    "name": nm,
                    "description": ("%s %s" % (pname, desc)).strip(),
                    "position": "main",
                    "components": [],
                    "priority": "high",
                    "page_route": route,
                }
            )
            mid += 1

    for fi, f in enumerate(normalized.get("features") or []):
        if isinstance(f, dict):
            nm = f.get("name") or "功能"
            desc = f.get("description") or ""
            pr = f.get("priority") or "medium"
        else:
            nm = str(f)
            desc = ""
            pr = "medium"
        modules.append(
            {
                "id": "feat_%s" % fi,
                "name": nm,
                "description": desc,
                "position": "main",
                "components": [],
                "priority": pr if pr in ("high", "medium", "low") else "medium",
            }
        )

    if not modules:
        modules.append(
            {
                "id": "main_content",
                "name": "主内容区",
                "description": "根据需求生成的主要内容",
                "position": "main",
                "components": [],
                "priority": "high",
            }
        )

    interactions: List[Dict[str, Any]] = []
    for pi, p in enumerate(pages):
        if not isinstance(p, dict):
            continue
        for ii, it in enumerate(p.get("interactions") or []):
            if isinstance(it, dict):
                interactions.append(
                    {
                        "id": it.get("id") or ("p%s_i%s" % (pi, ii)),
                        "trigger": it.get("trigger") or "",
                        "action": it.get("action") or "",
                        "target": it.get("target") or "",
                        "event_type": it.get("event_type") or "click",
                    }
                )
            elif isinstance(it, str) and it.strip():
                interactions.append(
                    {
                        "id": "p%s_i%s" % (pi, ii),
                        "trigger": it.strip(),
                        "action": it.strip(),
                        "target": "",
                        "event_type": "click",
                    }
                )

    data_model: List[Dict[str, Any]] = []
    for obj in normalized.get("data_objects") or []:
        if isinstance(obj, dict):
            name = obj.get("name") or "Entity"
            attrs = obj.get("attributes") or []
            fields = [{"name": str(a), "label": str(a), "type": "text", "required": False} for a in attrs if a]
            data_model.append({"entity": name, "fields": fields})
        else:
            data_model.append({"entity": str(obj), "fields": []})

    nav_t = (product.get("navigation") or {}).get("type") or "top"
    if nav_t not in _NAV_TYPES:
        nav_t = "top"

    return normalize_requirements(
        {
            "page_info": {
                "title": str(title)[:120],
                "type": page_type,
                "description": (product.get("summary") or normalized.get("notes") or "")[:500],
            },
            "functional_modules": modules,
            "interactions": interactions,
            "data_model": data_model,
            "visual_style": {
                "theme": "modern",
                "color_scheme": "blue",
                "primary_color": "#3B82F6",
                "layout": "single_column",
                "navigation_type": nav_t,
                "font_family": "Inter",
                "responsive": True,
            },
        }
    )


def _ensure_system_modules(product: Dict[str, Any]) -> None:
    """规范化 system_modules；子模块统一为字符串列表。"""
    raw = product.get("system_modules")
    if not isinstance(raw, list):
        product["system_modules"] = []
        return
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(raw):
        if not isinstance(m, dict):
            continue
        sm = m.get("sub_modules")
        sub_list: List[str] = []
        if isinstance(sm, list):
            for x in sm:
                if isinstance(x, dict) and x.get("name"):
                    s = str(x.get("name") or "").strip()
                    if s:
                        sub_list.append(s[:200])
                elif x is not None:
                    s = str(x).strip()
                    if s:
                        sub_list.append(s[:200])
        pids_raw = m.get("page_ids")
        if not isinstance(pids_raw, list):
            pids_raw = []
        name = str(m.get("name") or "").strip() or ("模块%s" % (i + 1))
        out.append(
            {
                "id": str(m.get("id") or _slug(name, "sysm-%s" % i))[:64],
                "name": name[:120],
                "parent_id": str(m.get("parent_id") or "").strip()[:64],
                "sub_modules": sub_list[:30],
                "page_ids": [str(x).strip() for x in pids_raw if str(x).strip()][:20],
                "notes": str(m.get("notes") or "")[:300],
            }
        )
    product["system_modules"] = out


def _empty_product() -> Dict[str, Any]:
    return {
        "pages": [
            {
                "name": "首页",
                "route": "/home",
                "modules": ["主内容"],
                "interactions": [],
            }
        ],
        "system_modules": [],
        "navigation": {"type": "", "links": []},
        "user_flows": [],
        "summary": "",
    }


async def product_design_node(state: DocToPrototypeState) -> Dict[str, Any]:
    """由 normalized_spec 与需求正文摘录生成 product_spec（含文档对齐的 system_modules）。"""
    normalized = state.get("normalized_spec") or {}
    doc_raw = (state.get("requirements_doc") or "").strip()
    if len(doc_raw) > PRODUCT_DESIGN_DOC_EXCERPT_CHARS:
        doc = doc_raw[:PRODUCT_DESIGN_DOC_EXCERPT_CHARS] + "\n\n…(正文截取前 %s 字)" % PRODUCT_DESIGN_DOC_EXCERPT_CHARS
    else:
        doc = doc_raw or "（无正文）"

    llm = get_llm_for_planner()
    prompt = f"""你是信息架构与产品经理。根据**归一化业务规格**与**需求正文摘录**，做原型级的**系统模块设计**：页面拆分、导航与用户流程须与文档中的模块/子模块划分（若有）一致。

# 归一化规格（JSON）
{json.dumps(normalized, ensure_ascii=False)}

# 需求正文摘录（用于识别文档已声明的模块、子模块、章节、功能包等层级）
{doc}

---

输出严格 JSON：
{{
  "summary": "产品一句话概述",
  "system_modules": [
    {{
      "id": "模块英文短横线id",
      "name": "与文档一致的模块名称",
      "parent_id": "上级模块 id，无则空字符串",
      "sub_modules": ["文档中的子模块名称，按原文层级列出"],
      "page_ids": ["该模块主要落地的页面 id，须与下方 pages[].id 一致"],
      "notes": "可选：与文档章节的对应说明"
    }}
  ],
  "pages": [
    {{
      "name": "页面名称",
      "route": "#/page-id",
      "id": "page-id",
      "modules": ["页内业务区块：优先使用文档子模块/能力点表述"],
      "interactions": [{{ "id": "x", "trigger": "用户操作", "action": "系统反馈或跳转说明", "target": "目标页id或留空" }}]
    }}
  ],
  "navigation": {{ "type": "tab|sidebar|top", "links": [{{ "label": "", "target_page_id": "" }}] }},
  "user_flows": [{{ "name": "", "steps": ["步骤"] }}]
}}

规则：
1. **文档优先**：若正文或规格中已定义系统模块、子模块、功能分包、章节型结构，必须优先按**文档用词与层级**填写 `system_modules`，并用 `page_ids` 关联到页面；页内 `modules` 应与对应子模块或能力对齐。
2. **无文档模块时**：若全文未划分模块，则 `system_modules` 输出空数组 `[]`，再依据归一化 `features` / `business_flows` 推导页面与 `pages[].modules`。
3. 简单场景可 1 页；复杂时按任务分 2～12 页；路由使用 hash，如 #/order-list。`pages[].modules` 不写具体 UI 组件名。
4. `navigation.type` 必须三选一：`top`、`sidebar`（后台/多任务且页数≥2 时优先）、`tab`。`links` 的 `target_page_id` 对应各页 `id`。
5. 仅返回 JSON。"""

    t0 = time.perf_counter()
    try:
        resp = await llm.ainvoke(prompt)
        product = parse_json_safely(resp.content)
        if not isinstance(product, dict) or not product.get("pages"):
            product = _empty_product()
        if not isinstance(product.get("navigation"), dict):
            product["navigation"] = {"type": "", "links": []}
        product.setdefault("user_flows", [])
        product.setdefault("summary", "")
        _ensure_system_modules(product)
        _normalize_product_navigation(product, normalized)

        site_map = _product_pages_to_site_map(product)
        if not site_map:
            site_map = [
                {
                    "id": "home",
                    "title": "首页",
                    "route": "#/home",
                    "summary": product.get("summary", "")[:200],
                    "order": 0,
                }
            ]
        mode = _infer_mode(site_map)
        extracted = _build_legacy_extracted(normalized, product)
        n_mod = len(product.get("system_modules") or [])

        logger.info(
            "[产品设计] 完成，共 %s 页，系统模块 %s 个，模式 %s，耗时 %.1fs",
            len(site_map),
            n_mod,
            mode,
            time.perf_counter() - t0,
        )
        return {
            "product_spec": product,
            "site_map": site_map,
            "generation_mode": mode,
            "extracted_requirements": extracted,
        }
    except Exception as e:
        logger.error("[产品设计] 失败，使用兜底: %s", e, exc_info=True)
        product = _empty_product()
        if not isinstance(product.get("navigation"), dict):
            product["navigation"] = {"type": "", "links": []}
        _ensure_system_modules(product)
        _normalize_product_navigation(product, normalized or {})
        site_map = _product_pages_to_site_map(product)
        extracted = _build_legacy_extracted(normalized or {}, product)
        return {
            "product_spec": product,
            "site_map": site_map,
            "generation_mode": _infer_mode(site_map),
            "extracted_requirements": extracted,
        }
