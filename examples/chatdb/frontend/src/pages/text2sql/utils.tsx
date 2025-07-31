import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { nord as codeTheme } from 'react-syntax-highlighter/dist/esm/styles/prism';
// 暂时注释掉 remarkGfm 以避免类型错误
// import remarkGfm from 'remark-gfm';

/**
 * 将数据转换为CSV格式的函数
 */
export const convertToCSV = (data: any[]): string => {
  if (!data || !data.length) return '';

  // 获取所有列名
  const headers = Object.keys(data[0]);

  // 创建CSV头行
  const headerRow = headers.join(',');

  // 创建数据行
  const rows = data.map(row => {
    return headers.map(header => {
      // 处理值中的特殊字符，如逗号、引号等
      const value = row[header];
      const valueStr = value === null || value === undefined ? '' : String(value);
      // 如果值包含逗号、引号或换行符，则用引号包裹并处理内部引号
      if (valueStr.includes(',') || valueStr.includes('"') || valueStr.includes('\n')) {
        return `"${valueStr.replace(/"/g, '""')}"`;
      }
      return valueStr;
    }).join(',');
  }).join('\n');

  // 返回完整的CSV内容
  return `${headerRow}\n${rows}`;
};

/**
 * 格式化文本展示组件 - 优化版
 */
export const FormattedOutput = ({ content, type, region }: { content: string, type: 'sql' | 'json' | 'markdown' | 'text', region?: string }) => {
  if (!content) {
    return <div className="text-gray-400 italic text-center p-2">暂无内容</div>;
  }

  // 预处理内容，修复常见的格式问题
  const preprocessContent = (rawContent: string, contentType: string): string => {
    let processed = rawContent;

    // 对Markdown内容进行特殊处理（对语句解释区域进行轻量化处理）
    if (contentType === 'markdown') {
      // 如果是语句解释区域，只进行基本的格式清理
      if (region === 'explanation') {
        // 只进行最基本的清理，保持markdown格式完整性
        processed = processed.replace(/\n{3,}/g, '\n\n'); // 清理多余空行
        processed = processed.replace(/^\s+|\s+$/g, ''); // 清理首尾空白
        return processed;
      }
      // 首先移除用户交互提示文本，但保留用户反馈内容
      processed = processed.replace(/Enter your response: 请输入修改建议或者直接点击同意(?=\s|$)/g, '');
      // 不完全移除用户已同意操作的标记，保留用户反馈部分
      processed = processed.replace(/---+\n### 用户已同意操作\n---+(?!\n### 用户反馈)/g, '---\n### 用户已同意操作\n---');
      processed = processed.replace(/分析已完成/g, '');

      // 先清理重复的内容
      processed = processed.replace(/(已找到以下相关表:[\s\S]*?)\1/g, '$1');
      processed = processed.replace(/(# SQL 命令生成报告)[\s\S]*?### 1\./g, '$1\n\n### 1.');
      processed = processed.replace(/生成报告\s*\n/g, '');

      // 修复特定的格式问题 - 添加换行
      processed = processed.replace(/正在分析查询并获取相关表结构\.\.\./g, '正在分析查询并获取相关表结构...\n');
      processed = processed.replace(/已找到以下相关表:/g, '已找到以下相关表:\n');
      processed = processed.replace(/表结构检索完成正在分析查询意图\.\.\./g, '表结构检索完成\n正在分析查询意图...\n');

      // 修复重复的标题问题
      processed = processed.replace(/### (\d+\.)### \1/g, '### $1');
      processed = processed.replace(/### (\d+\.) \. /g, '### $1 ');
      processed = processed.replace(/(\d+\.) \1/g, '$1');
      processed = processed.replace(/\.(\d+)\./g, '.$1');
      processed = processed.replace(/###\s*\n###/g, '###');
      processed = processed.replace(/值 值映射信息映射信息/g, '值映射信息');
      processed = processed.replace(/查询意图描述意图描述/g, '查询意图描述');
      processed = processed.replace(/需要使用的表使用的表名列表/g, '需要使用的表名列表');
      processed = processed.replace(/筛选条件筛选条件描述/g, '筛选条件描述');
      processed = processed.replace(/分组描述\s*\n\s*分组描述/g, '分组描述');
      processed = processed.replace(/排序描述\s*\n\s*排序描述/g, '排序描述');
      processed = processed.replace(/潜在歧义 潜在歧义与缺失与缺失信息/g, '潜在歧义与缺失信息');
      processed = processed.replace(/初步 初步的SQL的SQL查询结构草案/g, '初步的SQL查询结构草案');
      processed = processed.replace(/基于 基于以上分析的初步 SQL 查询 查询结构/g, '基于以上分析的初步SQL查询结构');

      // 修复数据库结构中的错误
      processed = processed.replace(/CREATE TABLE \[students\s*CREATE TABLE \[students\]/g, 'CREATE TABLE [students]');
      processed = processed.replace(/\]\s*\n\s*\(\s*\n\s*\[\s*\]\s*\n\s*\(/g, ']\n(');
      processed = processed.replace(/student_id\] INTEGER PRIMARY KEYstudent_id\] INTEGER PRIMARY KEY/g, 'student_id] INTEGER PRIMARY KEY');
      processed = processed.replace(/student ,\s*\[student/g, 'student_id ,\n   [student');
      processed = processed.replace(/_name\] VARCHAR\(_name\] VARCHAR\(/g, '_name] VARCHAR(');
      processed = processed.replace(/100\) 100\)/g, '100)');
      processed = processed.replace(/major\] VARCHAR\(100\)major\] VARCHAR\(100\)/g, 'major] VARCHAR(100)');
      processed = processed.replace(/\[{3}\[major\]/g, 'major');
      processed = processed.replace(/\[year_ofyear_of_enrollment\]/g, 'year_of_enrollment');
      processed = processed.replace(/enrollment\] INTEGER ,\s*\[ ,/g, 'enrollment] INTEGER ,');
      processed = processed.replace(/student_agestudent_age\] INTEGER\] INTEGER/g, 'student_age] INTEGER');
      processed = processed.replace(/\);\s*,\s*\);/g, ');');
      processed = processed.replace(/\[student_idstudent_id\] INTEGER PRIMARY KEY FOREIGN KEY FOREIGN KEY,/g, '[student_id] INTEGER PRIMARY KEY FOREIGN KEY,');
      processed = processed.replace(/,\s*,/g, ',');
      processed = processed.replace(/\[course \[course_id\]/g, '[course_id]');
      processed = processed.replace(/\[{3}\[score\]/g, '[score]');
      processed = processed.replace(/\[sem \[semester\]/g, '[semester]');

      // 修复SQL语句中的错误
      processed = processed.replace(/SELECT\s*\n\s*SELECT/g, 'SELECT');
      processed = processed.replace(/SELECT student(SELECT student)?_id,_id,/g, 'SELECT student_id,');
      processed = processed.replace(/student_name student_name/g, 'student_name');
      processed = processed.replace(/year, year_of_enrollment/g, 'year_of_enrollment');
      processed = processed.replace(/student_age student_age/g, 'student_age');
      processed = processed.replace(/FROM students\s*\n\s*FROM students/g, 'FROM students');
      processed = processed.replace(/\[([^\]]+)\]/g, '$1'); // 移除方括号

      // 修复字段列表中的错误
      processed = processed.replace(/students: student: student_id,/g, 'students: student_id,');
      processed = processed.replace(/student_name, major student_name, major/g, 'student_name, major');
      processed = processed.replace(/, year_of_en_of_enrollment,/g, ', year_of_enrollment,');
      processed = processed.replace(/rollment, student_age student_age/g, 'student_age');

      // 修复重复的段落
      processed = processed.replace(/(获取所有学生的基本信息)\s*\n\s*\1/g, '$1');
      processed = processed.replace(/(mysql)\s*\n\s*###\s*\n\s*###\s*\n\s*### 3/g, '$1\n\n### 3');
      processed = processed.replace(/###\s*\n\s*###/g, '###');

      // 修复特殊的格式问题
      processed = processed.replace(/\(\s*\n\s*\(/g, '(');
      processed = processed.replace(/\)\s*\n\s*\)/g, ')');
      processed = processed.replace(/\(\s*\n\s*不需要使用/g, '(不需要使用');
      processed = processed.replace(/聚合函数\s*\n\s*\)/g, '聚合函数)');
      processed = processed.replace(/\n-\s*\n-/g, '\n-');
      processed = processed.replace(/\n\s*\n-\s*\n/g, '\n\n- ');
      processed = processed.replace(/\n-\s*\n\s*-/g, '\n- ');
      processed = processed.replace(/\n\s*\n\s*###/g, '\n\n###');
      processed = processed.replace(/\n\s*\n\s*```/g, '\n\n```');
      processed = processed.replace(/```\s*\n\s*\n/g, '```\n');
      processed = processed.replace(/;\s*\n\s*```Enter/g, ';\n```\n\nEnter');

      // 移除多余的分析已完成文本
      processed = processed.replace(/分析已完成# SQL 命令生成报告/g, '# SQL 命令生成报告');

      // 1. 修复连续的换行问题，确保段落之间有空行
      processed = processed.replace(/\n{3,}/g, '\n\n');

      // 2. 修复标题前后的空行
      processed = processed.replace(/(\n)(#{1,6}\s+[^\n]+)/g, '$1\n$2');
      processed = processed.replace(/(#{1,6}\s+[^\n]+)(\n)/g, '$1\n$2');

      // 3. 修复列表项的格式
      processed = processed.replace(/(\n)([*-]\s+[^\n]+)(\n)(?![*-]\s+)/g, '$1$2\n$3');

      // 4. 修复代码块的格式
      processed = processed.replace(/(```[^\n]*)(\n)/g, '$1\n$2');
      processed = processed.replace(/(\n)(```)(\n)/g, '$1$2\n$3');

      // 5. 修复表格的格式
      processed = processed.replace(/\|\s*\n\s*\|/g, '|\n|');

      // 6. 修复数字列表标题格式，确保正确渲染
      processed = processed.replace(/(\n|^)(\d+\.)\s+([^\n]+)/g, '$1$2 $3');

      // 7. 修复标题格式，确保与数字之间有空格
      processed = processed.replace(/(#{1,6})(\d+\.)/g, '$1 $2');

      // 最后执行一次全面清理
      // 删除重复的段落
      processed = processed.replace(/(获取所有学生的基本信息)\s*\n\s*\1/g, '$1');
      processed = processed.replace(/(获取所有学生的基本信息)\s*\n\s*\n\s*\1/g, '$1');
      processed = processed.replace(/(mysql)\s*\n\s*###\s*\n\s*###\s*\n\s*### 3/g, '$1\n\n### 3');
      processed = processed.replace(/(mysql)\s*\n\s*\n\s*###\s*\n\s*###\s*\n\s*### 3/g, '$1\n\n### 3');

      // 清理重复的标题
      processed = processed.replace(/###\s*\n\s*###/g, '###');
      processed = processed.replace(/###\s*\n\s*\n\s*###/g, '###\n\n');

      // 清理重复的内容
      processed = processed.replace(/(已找到以下相关表:[\s\S]*?)\1/g, '$1');
      processed = processed.replace(/(# SQL 命令生成报告)[\s\S]*?### 1\./g, '$1\n\n### 1.');

      // 清理重复的字段列表
      processed = processed.replace(/students: student_id, student_name, major, year_of_enrollment, student_age\s*\n\s*\n\s*\(\s*\n\s*\(/g, 'students: student_id, student_name, major, year_of_enrollment, student_age\n\n(');

      // 清理重复的表连接描述
      processed = processed.replace(/- 不需要表连接\uff0c连接\uff0c因为所有需要因为所有需要的信息都在students表中students表中/g, '- 不需要表连接，因为所有需要的信息都在students表中');

      // 清理重复的筛选条件
      processed = processed.replace(/- 无筛选条件\uff0c需要返回所有学生记录\u3002\s*\n\s*###\s*\n\s*### 10\. 10\./g, '- 无筛选条件，需要返回所有学生记录。\n\n### 10.');

      // 清理重复的分组描述
      processed = processed.replace(/- 不需要分组不需要分组操作\u3002\s*\n\s*###\s*\n\s*操作\u3002\s*\n\s*###\s*\n\s*### 11\./g, '- 不需要分组操作。\n\n### 11.');

      // 清理重复的排序描述
      processed = processed.replace(/- 用户没有用户没有指定排序要求，要求，可以按默认可以按默认顺序返回顺序返回结果（结果（通常为主通常为主键顺序）\u3002\s*\n\s*###\s*\n\s*键顺序）\u3002\s*\n\s*###\s*\n\s*### 12/g, '- 用户没有指定排序要求，可以按默认顺序返回结果（通常为主键顺序）。\n\n### 12');

      // 清理SQL语句中的错误
      processed = processed.replace(/```sql\s*([^`]*)```/g, (match, sqlContent) => {
        // 清理SQL代码块内的格式问题
        let cleanedSql = sqlContent
          .replace(/\s*SELECT\s+SELECT\s*/g, 'SELECT ')
          .replace(/\s*FROM\s+FROM\s*/g, 'FROM ')
          .replace(/(\w+)\s+\1/g, '$1')
          .replace(/\s+;\s+/g, ';\n')
          .replace(/--\s*\n\s*--/g, '--')
          .replace(/SELECT\s*\n\s*SELECT/g, 'SELECT')
          .replace(/FROM students\s*\n\s*FROM students/g, 'FROM students')
          .replace(/student_id student_id/g, 'student_id')
          .replace(/student_name, student_name/g, 'student_name')
          .replace(/major, major/g, 'major')
          .replace(/year_of_enrollment, year_of_enrollment/g, 'year_of_enrollment')
          .replace(/student_age\s*\n\s*FROM/g, 'student_age\nFROM')
          .trim();

        return '```sql\n' + cleanedSql + '\n```';
      });

      // 最后清理多余的空行
      processed = processed.replace(/\n{3,}/g, '\n\n');
      processed = processed.replace(/```\s*\n\s*\n/g, '```\n');
      processed = processed.replace(/\n\s*\n```/g, '\n```');
      processed = processed.replace(/;\s*\n\s*```Enter/g, ';\n```\n\nEnter');
    }

    return processed;
  };

  // 预处理内容
  const processedContent = preprocessContent(content, type);

  try {
    switch (type) {
      case 'json':
        try {
          // 尝试解析JSON
          const parsedJson = JSON.parse(processedContent);
          return (
            <SyntaxHighlighter
              language="json"
              style={codeTheme}
              showLineNumbers={true}
              startingLineNumber={1}
              wrapLines={true}
              wrapLongLines={true}
            >
              {JSON.stringify(parsedJson, null, 2)}
            </SyntaxHighlighter>
          );
        } catch (e) {
          // 如果解析失败，作为普通文本显示
          return <div className="whitespace-pre-wrap">{processedContent}</div>;
        }

      case 'sql':
        return (
          <SyntaxHighlighter
            language="sql"
            style={codeTheme}
            showLineNumbers={true}
            startingLineNumber={1}
            wrapLines={true}
            wrapLongLines={true}
          >
            {processedContent}
          </SyntaxHighlighter>
        );

      case 'markdown':
        try {
          return (
            <ReactMarkdown
              // 暂时移除 remarkPlugins 以避免类型错误
              // remarkPlugins={[remarkGfm]}
              components={{
                pre({ node, ...props }) {
                  return <pre className="rounded-md bg-gray-100 dark:bg-gray-800/70 p-2 my-4 overflow-auto" {...props} />;
                },
                code({ node, className, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !props.inline && match ? (
                    <SyntaxHighlighter
                      language={match[1]}
                      style={codeTheme}
                      showLineNumbers={true}
                      startingLineNumber={1}
                      PreTag="div"
                      wrapLines={true}
                      wrapLongLines={true}
                    >
                      {String(props.children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={`${className || ''} px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 text-sm font-mono`} {...props} />
                  );
                },
                table({ node, ...props }) {
                  return (
                    <div className="overflow-x-auto my-6 rounded-md border border-gray-200 dark:border-gray-700">
                      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700" {...props} />
                    </div>
                  );
                },
                thead({ node, ...props }) {
                  return <thead className="bg-gray-50 dark:bg-gray-800" {...props} />;
                },
                th({ node, ...props }) {
                  return <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider" {...props} />;
                },
                td({ node, ...props }) {
                  return <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700" {...props} />;
                },
                h1({ node, children, ...props }) {
                  return <h1 className="text-2xl font-bold mt-6 mb-4 pb-2 border-b border-gray-200 dark:border-gray-700" {...props}>{children}</h1>;
                },
                h2({ node, children, ...props }) {
                  return <h2 className="text-xl font-bold mt-5 mb-3 pb-1 border-b border-gray-200 dark:border-gray-700" {...props}>{children}</h2>;
                },
                h3({ node, children, ...props }) {
                  return <h3 className="text-lg font-bold mt-4 mb-2" {...props}>{children}</h3>;
                },
                h4({ node, children, ...props }) {
                  return <h4 className="text-base font-semibold mt-3 mb-2" {...props}>{children}</h4>;
                },
                ul({ node, ...props }) {
                  return <ul className="list-disc pl-6 my-4 space-y-2" {...props} />;
                },
                ol({ node, start, ...props }: any) {
                  return <ol className="list-decimal pl-6 my-4 space-y-2" start={start || 1} {...props} />;
                },
                li({ node, ...props }) {
                  return <li className="my-1" {...props} />;
                },
                p({ node, ...props }) {
                  return <p className="my-4 leading-relaxed" {...props} />;
                },
                blockquote({ node, ...props }) {
                  return <blockquote className="pl-4 border-l-4 border-gray-200 dark:border-gray-700 my-4 italic text-gray-600 dark:text-gray-300" {...props} />;
                },
                hr({ node, ...props }) {
                  return <hr className="my-6 border-gray-200 dark:border-gray-700" {...props} />;
                },
                a({ node, children, ...props }) {
                  return <a className="text-blue-600 dark:text-blue-400 hover:underline" {...props}>{children}</a>;
                },
                img({ node, alt, ...props }) {
                  return <img className="max-w-full h-auto my-4 rounded-md" alt={alt || ''} {...props} />;
                },
              }}
            >
              {processedContent}
            </ReactMarkdown>
          );
        } catch (error) {
          return (
            <div className="whitespace-pre-wrap p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800/50 rounded-md">
              <p className="text-red-500 dark:text-red-400 font-bold mb-2">Markdown渲染错误</p>
              <div className="overflow-auto max-h-[300px] font-mono text-sm">{processedContent}</div>
            </div>
          );
        }

      default:
        return <div className="whitespace-pre-wrap leading-relaxed">{processedContent}</div>;
    }
  } catch (error) {
    return <div className="whitespace-pre-wrap text-red-500 p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800/50 rounded-md">
      <p className="font-bold mb-2">渲染错误</p>
      <div className="overflow-auto max-h-[300px] font-mono text-sm">{processedContent}</div>
    </div>;
  }
};
