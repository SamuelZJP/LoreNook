from backend.modules.chats.preview import LIMIT, last_line


def test_last_line_reads_the_content_body_without_tags():
    assert last_line("<think>不显示</think><content>第一行\n<b>最后</b>一行\n\n</content><status>好感 3</status>") == "最后一行"


def test_last_line_falls_back_to_the_whole_text():
    assert last_line("没有标签的开场\n第二句") == "第二句"
    assert last_line("<content>未闭合") == "未闭合"
    assert last_line("") == last_line("<content>  </content>") == ""


def test_last_line_is_shortened():
    line = last_line("字" * (LIMIT + 10))
    assert len(line) == LIMIT and line.endswith("…")


def test_last_line_drops_markdown_marks():
    assert last_line("<content>“我明白了，**继续吧**。”</content>") == "“我明白了，继续吧。”"
    assert last_line("> 引用里的 `代码` 和 ~~删除~~") == "引用里的 代码 和 删除"
