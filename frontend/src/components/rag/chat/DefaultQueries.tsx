import React from 'react';
import { Card, Row, Col, Space, Typography } from 'antd';
import {
  BulbOutlined,
  ExperimentOutlined,
  FireOutlined,
  GlobalOutlined,
  MessageOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  BookOutlined
} from '@ant-design/icons';
import { DefaultQueriesProps } from '@/types/rag';

const { Text } = Typography;

const DefaultQueries: React.FC<DefaultQueriesProps> = ({ setQuery, mode }) => {
  const defaultRagQueries = [
    {
      query: '上传文档的主要主题是什么？',
      icon: <BulbOutlined style={{ color: '#faad14' }} />,
      description: '分析文档主题'
    },
    {
      query: '为我总结关键要点。',
      icon: <BookOutlined style={{ color: '#722ed1' }} />,
      description: '提取核心内容'
    },
    {
      query: '您在文档中发现了什么问题？',
      icon: <QuestionCircleOutlined style={{ color: '#f5222d' }} />,
      description: '问题识别'
    },
    {
      query: '这些文档之间是如何相互关联的？',
      icon: <GlobalOutlined style={{ color: '#52c41a' }} />,
      description: '关联分析'
    },
    {
      query: '文档中提到的关键数据有哪些？',
      icon: <SearchOutlined style={{ color: '#1890ff' }} />,
      description: '数据提取'
    },
    {
      query: '基于这些文档，有什么建议？',
      icon: <ExperimentOutlined style={{ color: '#13c2c2' }} />,
      description: '智能建议'
    },
  ];

  const defaultAgentQueries = [
    {
      query: '你好！今天过得怎么样？',
      icon: <MessageOutlined style={{ color: '#faad14' }} />,
      description: '友好问候'
    },
    {
      query: '你能帮我更好地理解我的文档吗？',
      icon: <BookOutlined style={{ color: '#722ed1' }} />,
      description: '文档理解'
    },
    {
      query: '智能RAG从长远来看如何帮助我？',
      icon: <BulbOutlined style={{ color: '#f5222d' }} />,
      description: '价值分析'
    },
    {
      query: '你能做的最酷的事情是什么？',
      icon: <FireOutlined style={{ color: '#52c41a' }} />,
      description: '能力展示'
    },
    {
      query: '如何提高文档搜索的准确性？',
      icon: <SearchOutlined style={{ color: '#1890ff' }} />,
      description: '优化建议'
    },
    {
      query: '帮我分析一下当前的知识库结构',
      icon: <GlobalOutlined style={{ color: '#13c2c2' }} />,
      description: '结构分析'
    },
  ];

  const getQueriesBasedOnMode = (mode: 'rag' | 'rag_agent') => {
    if (mode === 'rag') {
      return defaultRagQueries;
    } else if (mode === 'rag_agent') {
      return defaultAgentQueries;
    } else {
      return defaultRagQueries;
    }
  };

  const defaultQueries = getQueriesBasedOnMode(mode);

  return (
    <div style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '24px' }}>
        <Text type="secondary">
          {mode === 'rag' ? '试试这些问题来探索您的文档：' : '开始对话，试试这些话题：'}
        </Text>
      </div>

      <Row gutter={[16, 16]}>
        {defaultQueries.map(({ query, icon, description }, index) => (
          <Col xs={24} sm={12} md={8} key={index}>
            <Card
              hoverable
              size="small"
              style={{
                height: '100px',
                cursor: 'pointer',
                borderRadius: '8px',
                transition: 'all 0.3s ease',
              }}
              bodyStyle={{
                padding: '12px',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
              onClick={() => setQuery(query)}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
              }}
            >
              <div>
                <Space align="start" style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '20px' }}>
                    {icon}
                  </div>
                  <Text
                    strong
                    style={{
                      fontSize: '12px',
                      color: '#666',
                      lineHeight: '1.2'
                    }}
                  >
                    {description}
                  </Text>
                </Space>

                <Text
                  style={{
                    fontSize: '13px',
                    lineHeight: '1.4',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {query}
                </Text>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <div style={{ textAlign: 'center', marginTop: '24px' }}>
        <Text type="secondary" style={{ fontSize: '12px' }}>
          点击任意卡片开始对话，或者在下方输入框中输入您的问题
        </Text>
      </div>
    </div>
  );
};

export default DefaultQueries;
