import streamlit as st
import asyncio
import os
from tag_down3 import run_tag_down  # 假设 tag_down2.py 中导出了 run_tag_down 函数

# 设置页面配置
st.set_page_config(page_title="Twitter Crawler", layout="wide", initial_sidebar_state="expanded")

def main():
    # 页面标题和简介
    st.title("Twitter Crawler")
    st.markdown("""
    这是一个基于 Streamlit 的 Twitter 爬虫工具，允许你下载带有指定标签或搜索条件的推文、媒体或文本内容。
    请在左侧栏中配置参数，然后点击“开始下载”按钮。任务完成后，结果将显示在主页面。
    """)

    # 侧边栏配置区域
    with st.sidebar:
        st.header("配置参数")

        # Cookie 输入
        cookie = st.text_area(
            "Twitter Cookie",
            height=100,
            help="从浏览器中获取 Twitter 的 Cookie，需包含 `auth_token` 和 `ct0` 字段，格式如：`auth_token=xxx; ct0=xxx;`。请确保 Cookie 有效，否则无法访问 API。"
        )

        # Tag 输入
        tag = st.text_input(
            "标签 (Tag)",
            value="#ig",
            help="输入带 # 的标签（如 #ig），或留空以使用 Filter 条件。文件夹将以此命名（特殊字符会被移除）。"
        )

        # Filter 输入
        _filter = st.text_input(
            "高级搜索条件 (Filter)",
            value="filter:links -filter:replies until:2025-03-28 since:2025-03-27",
            help="输入 Twitter 高级搜索条件，例如 `filter:links -filter:replies until:2023-10-01 since:2023-09-01`。请将双引号改为单引号。参考：https://x.com/search-advanced"
        )

        # 下载数量
        down_count = st.number_input(
            "下载数量 (Download Count)",
            min_value=50,
            max_value=10000,
            value=100,
            step=50,
            help="指定要下载的推文数量，建议为 50 的倍数，最小值为 50。"
        )

        # Media Latest 选项
        media_latest = st.checkbox(
            "从 [最新] 标签页下载",
            value=True,
            help="勾选时从 [最新] 标签页下载媒体，取消勾选时从 [媒体] 标签页下载。与文本模式无关。"
        )

        # Text Download 选项
        text_down = st.checkbox(
            "下载文本内容",
            value=False,
            help="勾选时仅下载文本内容（不含媒体），会消耗更多 API 调用次数。建议避免使用 filter:links。"
        )

        # 美化侧边栏
        st.markdown("---")
        st.subheader("使用说明")
        st.markdown("""
        - **Cookie**: 从浏览器开发者工具中复制 Twitter 的 Cookie。
        - **Tag**: 输入标签时，文件夹以此命名；若留空，则以 Filter 命名。
        - **Filter**: 可选，用于高级搜索，建议参考 Twitter 官方文档。
        - **下载数量**: 越大耗时越长，请根据需要调整。
        """)

        # 开始下载按钮
        start_button = st.button("开始下载", type="primary")

    # 主页面 - 显示运行状态和结果
    if start_button:
        # 验证输入
        if not cookie or "auth_token" not in cookie or "ct0" not in cookie:
            st.error("请提供有效的 Twitter Cookie，需包含 auth_token 和 ct0 字段！")
        else:
            with st.spinner("正在下载，请稍候..."):
                try:
                    # 运行异步函数
                    result = asyncio.run(run_tag_down(
                        cookie=cookie,
                        tag=tag,
                        _filter=_filter,
                        down_count=down_count,
                        media_latest=media_latest,
                        text_down=text_down
                    ))

                    # 显示成功信息
                    st.success("下载完成！")
                    st.write(f"文件保存路径: `{result['folder_path']}`")

                    # 提供 CSV 下载链接
                    if "csv_path" in result and os.path.exists(result["csv_path"]):
                        with open(result["csv_path"], "rb") as file:
                            st.download_button(
                                label="下载 CSV 文件",
                                data=file,
                                file_name=os.path.basename(result["csv_path"]),
                                mime="text/csv"
                            )

                except Exception as e:
                    st.error(f"下载过程中发生错误: {str(e)}")

    # 美化主页面
    st.markdown("---")
    st.markdown("""
    ### 关于
    本工具基于 Python 和 Streamlit 开发，支持从 Twitter 下载媒体或文本内容。
    如有问题，请检查 Cookie 是否有效，或调整搜索条件。
    """)

if __name__ == "__main__":
    main()