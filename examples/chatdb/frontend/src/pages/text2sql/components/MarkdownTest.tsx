import React, { useState } from 'react';
import { Button, Space } from 'antd';
import StreamingMarkdown from './StreamingMarkdown';

const MarkdownTest: React.FC = () => {
  const [content, setContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const testMarkdown = `## SQL 命令分析报告

### 1. 查询意图分析
用户希望查询学生的课程成绩情况，核心目标是：

### 2. 涉及的数据实体
**主要表：**
- students - 存储学生基本信息
- courses - 存储课程基本信息
- scores - 存储学生课程成绩关联关系

**关键字段：**
- students: student_id, student_name - 学生基本信息
- courses: course_id, course_name - 课程基本信息
- scores: student_id, course_id, score - 成绩关联信息

### 3. 表关系与连接
需要进行三表连接：
- scores 与 students 通过 student_id 连接
- scores 与 courses 通过 course_id 连接

### 4. 查询条件分析
**筛选条件：**
- 无特殊筛选条件
- 需要显示所有学生的所有课程成绩

**分组要求：**
无需分组

**排序要求：**
可按学生ID或成绩排序

### 5. SQL结构框架
\`\`\`sql
-- 基于分析的SQL查询结构
SELECT s.student_id, s.student_name, c.course_id, c.course_name, sc.score
FROM students s
JOIN scores sc ON s.student_id = sc.student_id
JOIN courses c ON sc.course_id = c.course_id
ORDER BY s.student_id, c.course_id
\`\`\`

### 6. 潜在问题与建议
- 需要确认是否包含没有成绩的学生
- 建议添加成绩范围筛选条件

---
*分析完成，可为SQL生成提供指导*`;

  const simulateStreaming = () => {
    setContent('');
    setIsStreaming(true);

    let index = 0;
    const interval = setInterval(() => {
      if (index < testMarkdown.length) {
        // 每次添加1-5个字符，模拟真实的流式输出
        const chunkSize = Math.min(Math.random() * 5 + 1, testMarkdown.length - index);
        const chunk = testMarkdown.substring(index, index + chunkSize);
        setContent(prev => prev + chunk);
        index += chunkSize;
      } else {
        setIsStreaming(false);
        clearInterval(interval);
      }
    }, 50); // 每50ms添加一块内容
  };

  const setFullContent = () => {
    setContent(testMarkdown);
    setIsStreaming(false);
  };

  const clearContent = () => {
    setContent('');
    setIsStreaming(false);
  };

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
      <h2>StreamingMarkdown 组件测试</h2>

      <Space style={{ marginBottom: '16px' }}>
        <Button onClick={simulateStreaming} type="primary">
          模拟流式输出
        </Button>
        <Button onClick={setFullContent}>
          显示完整内容
        </Button>
        <Button onClick={clearContent}>
          清空内容
        </Button>
      </Space>

      <div style={{
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        padding: '16px',
        backgroundColor: '#fff',
        minHeight: '400px'
      }}>
        <h3>渲染结果：</h3>
        <StreamingMarkdown
          content={content}
          isStreaming={isStreaming}
          className="test-markdown"
        />
      </div>

      <div style={{
        marginTop: '16px',
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        padding: '16px',
        backgroundColor: '#f5f5f5'
      }}>
        <h3>原始内容（用于对比）：</h3>
        <pre style={{
          whiteSpace: 'pre-wrap',
          fontSize: '12px',
          maxHeight: '200px',
          overflow: 'auto'
        }}>
          {JSON.stringify(content, null, 2)}
        </pre>
      </div>
    </div>
  );
};

export default MarkdownTest;
