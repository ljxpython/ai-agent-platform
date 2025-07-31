// 混合检索示例面板组件

import React, { useState, useEffect } from 'react';
import { Card, Tag, Progress, Tooltip, Button, Space, Collapse, Empty, Spin } from 'antd';
import {
  BulbOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';
import { hybridQAService } from '../../../services/hybridQA';
import type { SimilarQAPair } from '../../../types/hybridQA';
import '../../../styles/HybridExamples.css';

const { Panel } = Collapse;

interface HybridExamplesPanelProps {
  query: string;
  connectionId: number | null;
  schemaContext?: any;
  visible: boolean;
  onExampleSelect?: (example: SimilarQAPair) => void;
  onClose?: () => void;
}

const HybridExamplesPanel: React.FC<HybridExamplesPanelProps> = ({
  query,
  connectionId,
  schemaContext,
  visible,
  onExampleSelect,
  onClose
}) => {
  const [examples, setExamples] = useState<SimilarQAPair[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (visible && query.trim() && connectionId) {
      searchExamples();
    }
  }, [visible, query, connectionId, schemaContext]); // eslint-disable-line react-hooks/exhaustive-deps

  const searchExamples = async () => {
    if (!query.trim() || !connectionId) return;

    setLoading(true);
    setError(null);

    try {
      const results = await hybridQAService.getRecommendedExamples(
        query,
        connectionId,
        schemaContext,
        5
      );
      setExamples(results);
    } catch (err) {
      setError('获取相似示例失败');
      console.error('获取相似示例失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const getQueryTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      'SELECT': 'blue',
      'JOIN': 'green',
      'AGGREGATE': 'orange',
      'GROUP_BY': 'purple',
      'ORDER_BY': 'cyan'
    };
    return colors[type] || 'default';
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return '#52c41a';
    if (score >= 0.6) return '#faad14';
    return '#f5222d';
  };

  const formatSQL = (sql: string) => {
    // 简单的SQL格式化
    return sql
      .replace(/\bSELECT\b/gi, '\nSELECT')
      .replace(/\bFROM\b/gi, '\nFROM')
      .replace(/\bWHERE\b/gi, '\nWHERE')
      .replace(/\bJOIN\b/gi, '\nJOIN')
      .replace(/\bGROUP BY\b/gi, '\nGROUP BY')
      .replace(/\bORDER BY\b/gi, '\nORDER BY')
      .trim();
  };

  const renderScoreBreakdown = (example: SimilarQAPair) => (
    <div className="score-breakdown">
      <div className="score-item">
        <span>语义相似度:</span>
        <Progress
          percent={Math.round(example.semantic_score * 100)}
          size="small"
          strokeColor="#1890ff"
          showInfo={false}
        />
        <span className="score-value">{(example.semantic_score * 100).toFixed(1)}%</span>
      </div>
      <div className="score-item">
        <span>结构相似度:</span>
        <Progress
          percent={Math.round(example.structural_score * 100)}
          size="small"
          strokeColor="#52c41a"
          showInfo={false}
        />
        <span className="score-value">{(example.structural_score * 100).toFixed(1)}%</span>
      </div>
      <div className="score-item">
        <span>模式匹配度:</span>
        <Progress
          percent={Math.round(example.pattern_score * 100)}
          size="small"
          strokeColor="#faad14"
          showInfo={false}
        />
        <span className="score-value">{(example.pattern_score * 100).toFixed(1)}%</span>
      </div>
      <div className="score-item">
        <span>质量分数:</span>
        <Progress
          percent={Math.round(example.quality_score * 100)}
          size="small"
          strokeColor="#722ed1"
          showInfo={false}
        />
        <span className="score-value">{(example.quality_score * 100).toFixed(1)}%</span>
      </div>
    </div>
  );

  if (!visible) return null;

  return (
    <div className="hybrid-examples-panel">
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>
              <BulbOutlined style={{ marginRight: 8, color: '#faad14' }} />
              智能推荐示例
            </span>
            <Button type="text" size="small" onClick={onClose}>
              ×
            </Button>
          </div>
        }
        size="small"
        className="examples-card"
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <p style={{ marginTop: 16, color: '#666' }}>正在搜索相似示例...</p>
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <p style={{ color: '#ff4d4f' }}>{error}</p>
            <Button type="primary" size="small" onClick={searchExamples}>
              重试
            </Button>
          </div>
        ) : examples.length === 0 ? (
          <Empty
            description="暂无相似示例"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          <div className="examples-list">
            <div style={{ marginBottom: 16, fontSize: '12px', color: '#666' }}>
              找到 {examples.length} 个相关示例，按相关度排序
            </div>

            <Collapse size="small" ghost>
              {examples.map((example, index) => (
                <Panel
                  key={example.qa_pair.id}
                  header={
                    <div className="example-header">
                      <div className="example-title">
                        <span className="example-index">#{index + 1}</span>
                        <span className="example-question" title={example.qa_pair.question}>
                          {example.qa_pair.question.length > 50
                            ? `${example.qa_pair.question.substring(0, 50)}...`
                            : example.qa_pair.question
                          }
                        </span>
                      </div>
                      <div className="example-meta">
                        <Tag color={getQueryTypeColor(example.qa_pair.query_type)}>
                          {example.qa_pair.query_type}
                        </Tag>
                        <Progress
                          percent={Math.round(example.final_score * 100)}
                          size="small"
                          strokeColor={getScoreColor(example.final_score)}
                          style={{ width: 60 }}
                        />
                        {example.qa_pair.verified && (
                          <Tooltip title="已验证的高质量示例">
                            <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          </Tooltip>
                        )}
                      </div>
                    </div>
                  }
                  extra={
                    <Space size="small" onClick={(e) => e.stopPropagation()}>
                      <Tooltip title="使用此示例">
                        <Button
                          type="text"
                          size="small"
                          icon={<ThunderboltOutlined />}
                          onClick={() => onExampleSelect?.(example)}
                        />
                      </Tooltip>
                    </Space>
                  }
                >
                  <div className="example-content">
                    <div className="example-section">
                      <div className="section-title">
                        <DatabaseOutlined style={{ marginRight: 4 }} />
                        SQL语句
                      </div>
                      <pre className="sql-code">
                        {formatSQL(example.qa_pair.sql)}
                      </pre>
                    </div>

                    <div className="example-section">
                      <div className="section-title">
                        <RobotOutlined style={{ marginRight: 4 }} />
                        推荐理由
                      </div>
                      <p className="explanation">{example.explanation}</p>
                    </div>

                    <div className="example-section">
                      <div className="section-title">详细评分</div>
                      {renderScoreBreakdown(example)}
                    </div>

                    <div className="example-footer">
                      <Space>
                        <span>难度: {example.qa_pair.difficulty_level}/5</span>
                        <span>成功率: {(example.qa_pair.success_rate * 100).toFixed(1)}%</span>
                        {example.qa_pair.used_tables.length > 0 && (
                          <span>
                            涉及表: {example.qa_pair.used_tables.map(table => (
                              <Tag key={table}>{table}</Tag>
                            ))}
                          </span>
                        )}
                      </Space>
                    </div>
                  </div>
                </Panel>
              ))}
            </Collapse>
          </div>
        )}
      </Card>
    </div>
  );
};

export default HybridExamplesPanel;
