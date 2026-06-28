async function aiSummary(token, propertyName, modelType) {
  const model = modelType || "GLM-4-Flash"; // 智谱清言模型，GLM-4-Flash 是一个免费模型，其他模型需要付费

  if (!propertyName || !token) {
    new Notice("请设置密钥或属性名");
    return;
  }
  const { currentFile } = this;
  const file = currentFile;
  const fileContent = await app.vault.cachedRead(file);
  const title = file.basename;

  // 提示语
  const prompt = `
作为一个专业的编辑，当您接收到我发送的内容或链接时，你需要将原文章的内容总结后传达给读者，总结后的内容相对于原文章内容要简洁，字数不限，但不能丢失原文章核心思想或者观点，也绝对不能杜撰内容，同时需要让读者易于理解，通过较少的阅读时间达到与阅读原文一致的效果。

请直接输出总结内容即可，不需要包含原文内容。

你需要总结的文章

标题为：${title}

内容为：

${fileContent || ""}
`;

  var options = {
    method: "POST",
    url: "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: model,
      messages: [
        {
          role: "user",
          content: prompt,
        },
      ],
    }),
  };
  const response = await obsidian.requestUrl(options);
  const result = response.json;
  if (result.choices.length === 0) {
    new Notice("没有内容可输出");
    return;
  }

  const content = result.choices[0].message?.content;
  if (!content) {
    new Notice("没有内容可输出");
    return;
  }
  const prop = propertyName;
  app.fileManager.processFrontMatter(file, (frontmatter) => {
    frontmatter[prop] = content;
  });
}

exports.default = {
  entry: aiSummary,
  name: "aiSummary",
  description: `通过智谱清言的 API 来总结文章(默认使用的是免费模型 GLM-4-Flash)

  ==请先在 https://open.bigmodel.cn/ 注册并获取 API 密钥。==

  使用方法

\`aiSummary('你的密钥', '属性名')\`

  也可以指定其他付费模型，模型类型可以在 https://open.bigmodel.cn/console/modelcenter/square 查看

\`aiSummary('你的密钥', '属性名', 'glm-4-plus')\`

  `,
};
