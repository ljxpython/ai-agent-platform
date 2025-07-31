const fs = require('fs');
const path = require('path');

try {
  const filePath = path.join(__dirname, 'src', 'pages', 'text2sql', 'page.tsx');
  const content = fs.readFileSync(filePath, 'utf8');

  // 计算标签数量
  const divOpenCount = (content.match(/<div/g) || []).length;
  const divCloseCount = (content.match(/<\/div>/g) || []).length;
  const mainOpenCount = (content.match(/<main/g) || []).length;
  const mainCloseCount = (content.match(/<\/main>/g) || []).length;

  console.log(`<div> tags: ${divOpenCount}`);
  console.log(`</div> tags: ${divCloseCount}`);
  console.log(`<main> tags: ${mainOpenCount}`);
  console.log(`</main> tags: ${mainCloseCount}`);

  // 检查标签嵌套
  const lines = content.split('\n');
  let stack = [];
  let lineNumbers = [];

  lines.forEach((line, index) => {
    // 检查开始标签
    const openTags = line.match(/<(div|main)[^>]*>/g) || [];
    openTags.forEach(tag => {
      const tagName = tag.match(/<(div|main)/)[1];
      stack.push({ tag: tagName, line: index + 1 });
    });

    // 检查结束标签
    const closeTags = line.match(/<\/(div|main)>/g) || [];
    closeTags.forEach(tag => {
      const tagName = tag.match(/<\/(div|main)>/)[1];
      if (stack.length === 0) {
        console.log(`Extra closing tag </${tagName}> at line ${index + 1}`);
      } else {
        const lastTag = stack.pop();
        if (lastTag.tag !== tagName) {
          console.log(`Mismatched tags: <${lastTag.tag}> at line ${lastTag.line} and </${tagName}> at line ${index + 1}`);
          lineNumbers.push({ open: lastTag.line, close: index + 1 });
        }
      }
    });
  });

  if (stack.length > 0) {
    console.log('Unclosed tags:');
    stack.forEach(item => {
      console.log(`<${item.tag}> at line ${item.line}`);
    });
  }

  if (lineNumbers.length > 0) {
    console.log('Mismatched tag line numbers:');
    lineNumbers.forEach(item => {
      console.log(`Open: ${item.open}, Close: ${item.close}`);
    });
  }
} catch (err) {
  console.error('Error:', err);
}
