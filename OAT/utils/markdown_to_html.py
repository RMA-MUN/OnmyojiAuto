def markdown_to_html(markdown: str) -> str:
    """
    将Markdown格式的文本转成HTML的富文本
    """
    if not markdown:
        return "<p>暂无更新日志</p>"

    # 替换Markdown格式为HTML
    lines = markdown.split('\n')
    html_lines = []
    in_list = False
    in_code = False
    first_header_skipped = False

    for line in lines:
        # 处理代码块
        if line.startswith('```'):
            in_code = not in_code
            if in_code:
                html_lines.append('<pre><code>')
            else:
                html_lines.append('</code></pre>')
            continue

        if in_code:
            html_lines.append(line)
            continue

        # 处理标题，跳过第一个标题行（避免与版本信息重复）
        if line.startswith('# '):
            if not first_header_skipped:
                first_header_skipped = True
                continue
            html_lines.append(f'<h1>{line[2:]}</h1>')
            continue
        elif line.startswith('## '):
            html_lines.append(f'<h2>{line[3:]}</h2>')
            continue
        elif line.startswith('### '):
            html_lines.append(f'<h3>{line[4:]}</h3>')
            continue

        # 处理列表
        if line.startswith('- '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{line[2:]}</li>')
            continue
        elif in_list:
            html_lines.append('</ul>')
            in_list = False

        # 处理空行
        if not line.strip():
            if html_lines and not html_lines[-1].strip():
                continue
            html_lines.append('')
            continue

        # 处理普通行（包含粗体和斜体）
        processed_line = line
        # 处理粗体
        processed_line = processed_line.replace('**', '<strong>').replace('**', '</strong>')
        # 处理斜体
        processed_line = processed_line.replace('*', '<em>').replace('*', '</em>')
        html_lines.append(f'<p>{processed_line}</p>')

    # 关闭未关闭的标签
    if in_list:
        html_lines.append('</ul>')
    if in_code:
        html_lines.append('</code></pre>')

    return '\n'.join(html_lines)