// Editable example. Change fixed text here; logical roles need not match API roles.
// No exports/imports: the runtime calls these two synchronous functions.
const fixed = {
    openingModel: '<预设固定内容>',
    openingUser: '<预设固定内容>',
    historyPrefix: '<预设固定内容>',
    inputPrefix: '<前缀>',
    inputSuffix: '<后缀>',
    filler: '<填充>',
    beforeState: '<预设固定内容>',
    afterState: '<预设固定内容>',
    finalUser: '<预设固定内容>',
    systemPrefix: '<预设固定内容>',
    systemSuffix: '<预设固定内容>'
};

function build(materials) {
    const contents = [];
    const message = (role, text) => contents.push({role, parts: [{text}]});
    const wrapInput = text => fixed.inputPrefix + text + fixed.inputSuffix;
    message('model', fixed.openingModel);
    message('user', fixed.openingUser);

    // Keep compressed items in their selected chronological order.
    const history = materials.history.items.filter(item => item.kind !== 'round')
        .map(item => item.summary).join('\n');
    const first = materials.history.uses_compressed_history ? '' : materials.first_message;
    let pending = fixed.historyPrefix + first + history;
    for (const round of materials.history.items.filter(item => item.kind === 'round')) {
        message('model', pending + '\n' + wrapInput(round.user_input));
        message('user', fixed.filler);
        // Preserve all accepted assistant tags when resending history.
        pending = round.ai_output;
    }
    message('model', pending + '\n' + wrapInput(materials.user_input));
    message('user', fixed.openingUser);
    message('model', fixed.beforeState + '\n' + materials.state_yaml + '\n' + fixed.afterState);
    message('user', fixed.finalUser);

    const definitions = [...materials.character_definitions, ...materials.user_definitions]
        .map(item => item.content).join('\n');
    return {
        api_type: 'google_generate_content',
        body: {
            contents,
            generationConfig: {candidateCount: 1, maxOutputTokens: 65535, temperature: 1, topP: 0.98},
            systemInstruction: {parts: [{text: fixed.systemPrefix + '\n\n' + definitions + '\n' + fixed.systemSuffix}]},
            tools: [{functionDeclarations: [{
                name: 'game_content',
                description: '全部回复必须通过此工具的 content 参数输出；包含且仅包含一个闭合的 report_nya~ 和 content 区段。',
                parameters: {
                    type: 'OBJECT', properties: {content: {type: 'STRING'}}, required: ['content']
                }
            }]}],
            toolConfig: {functionCallingConfig: {mode: 'ANY', allowedFunctionNames: ['game_content']}}
        }
    };
}

function parse(response) {
    if (!Array.isArray(response.candidates) || response.candidates.length !== 1)
        throw new Error('需要且只能有一个候选回复');
    const candidate = response.candidates[0];
    if (candidate.finishReason !== 'STOP')
        throw new Error('回复未正常完成');
    const parts = candidate.content && candidate.content.parts;
    if (!Array.isArray(parts)) throw new Error('缺少回复 parts');
    const calls = parts.filter(part => part.functionCall).map(part => part.functionCall);
    if (calls.length !== 1 || calls[0].name !== 'game_content')
        throw new Error('需要唯一的 game_content 工具输出');
    const text = calls[0].args && calls[0].args.content;
    if (typeof text !== 'string') throw new Error('工具 content 必须是字符串');

    // Each required tag occurs once, closes correctly, and cannot contain the other.
    const sections = [];
    for (const name of ['report_nya~', 'content']) {
        const open = '<' + name + '>', close = '</' + name + '>';
        const start = text.indexOf(open), end = text.indexOf(close);
        if (start < 0 || end < start + open.length ||
            text.indexOf(open, start + open.length) !== -1 || text.indexOf(close, end + close.length) !== -1)
            throw new Error('标签缺失、重复或未正确闭合: ' + name);
        const inner = text.slice(start + open.length, end);
        if (!inner.trim()) throw new Error('标签内容不能为空: ' + name);
        sections.push({start, end: end + close.length});
    }
    sections.sort((a, b) => a.start - b.start);
    if (sections[0].end > sections[1].start) throw new Error('标签不能嵌套或交叉');
    // Exact source slices preserve the tags and content; discard surrounding prose.
    return sections.map(section => text.slice(section.start, section.end)).join('\n');
}
