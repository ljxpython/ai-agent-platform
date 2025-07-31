const fs = require('fs');
const path = require('path');

try {
  const filePath = path.join(__dirname, 'src', 'pages', 'text2sql', 'page.tsx');
  const content = fs.readFileSync(filePath, 'utf8');

  const lines = content.split('\n');
  let found = false;

  lines.forEach((line, index) => {
    if (line.includes('motion.') || line.includes('<motion.') || line.includes('</motion.')) {
      console.log(`Line ${index + 1}: ${line}`);
      found = true;
    }
  });

  if (!found) {
    console.log('No motion references found');
  }
} catch (err) {
  console.error('Error:', err);
}
