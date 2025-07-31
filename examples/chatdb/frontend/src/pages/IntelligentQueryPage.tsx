import React, { useState, useEffect } from 'react';
import {
  Card, Select, Input, Button, Table, Spin, message,
  Typography, Tabs, Divider
} from 'antd';
import { SendOutlined, CopyOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import * as api from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Title, Text } = Typography;
const { TabPane } = Tabs;

interface DBConnection {
  id: number;
  name: string;
}

interface QueryResult {
  sql: string;
  results: any[] | null;
  error: string | null;
  context: any | null;
}

const IntelligentQueryPage: React.FC = () => {
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<number | null>(null);
  const [query, setQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [columns, setColumns] = useState<any[]>([]);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    try {
      const response = await api.getConnections();
      setConnections(response.data);
    } catch (error) {
      message.error('获取连接失败');
      console.error(error);
    }
  };

  const handleConnectionChange = (value: number) => {
    setSelectedConnection(value);
    setResult(null);
  };

  const handleQueryChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuery(e.target.value);
  };

  const executeQuery = async () => {
    if (!selectedConnection) {
      message.error('请选择数据库连接');
      return;
    }

    if (!query.trim()) {
      message.error('请输入查询');
      return;
    }

    setLoading(true);
    try {
      const response = await api.executeQuery({
        connection_id: selectedConnection,
        natural_language_query: query
      });

      setResult(response.data);

      // Generate table columns from results
      if (response.data.results && response.data.results.length > 0) {
        const firstRow = response.data.results[0];
        const tableColumns = Object.keys(firstRow).map(key => ({
          title: key,
          dataIndex: key,
          key: key,
          sorter: (a: any, b: any) => {
            if (typeof a[key] === 'number') {
              return a[key] - b[key];
            }
            return String(a[key]).localeCompare(String(b[key]));
          }
        }));
        setColumns(tableColumns);
      } else {
        setColumns([]);
      }
    } catch (error) {
      message.error('执行查询失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => {
        message.success('已复制到剪贴板');
      },
      () => {
        message.error('复制失败');
      }
    );
  };

  return (
    <div>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <Title level={4}>智能查询</Title>
          <Select
            placeholder="选择数据库连接"
            style={{ width: 300 }}
            onChange={handleConnectionChange}
            value={selectedConnection || undefined}
          >
            {connections.map(conn => (
              <Option key={conn.id} value={conn.id}>{conn.name}</Option>
            ))}
          </Select>
        </div>

        <div style={{ marginBottom: 16 }}>
          <TextArea
            placeholder="用自然语言输入你的问题，例如：'去年东部地区销售量前5的产品是哪些？'"
            value={query}
            onChange={handleQueryChange}
            autoSize={{ minRows: 3, maxRows: 6 }}
            style={{ marginBottom: 8 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={executeQuery}
            loading={loading}
            disabled={!selectedConnection}
          >
            执行查询
          </Button>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Text>正在分析您的问题并生成SQL...</Text>
            </div>
          </div>
        )}

        {result && !loading && (
          <div>
            <Divider orientation="left">结果</Divider>

            <Tabs defaultActiveKey="1">
              <TabPane tab="生成的SQL" key="1">
                <div style={{ position: 'relative' }}>
                  <Button
                    icon={<CopyOutlined />}
                    style={{ position: 'absolute', top: 8, right: 8, zIndex: 1 }}
                    onClick={() => copyToClipboard(result.sql)}
                  >
                    复制
                  </Button>
                  <SyntaxHighlighter language="sql" style={vscDarkPlus}>
                    {result.sql}
                  </SyntaxHighlighter>
                </div>
              </TabPane>

              <TabPane tab="查询结果" key="2">
                {result.error ? (
                  <div style={{ color: 'red', marginBottom: 16 }}>
                    <Text type="danger">{result.error}</Text>
                  </div>
                ) : result.results && result.results.length > 0 ? (
                  <Table
                    columns={columns}
                    dataSource={result.results.map((item, index) => ({ ...item, key: index }))}
                    scroll={{ x: 'max-content' }}
                    pagination={{ pageSize: 10 }}
                  />
                ) : (
                  <Text>未找到结果</Text>
                )}
              </TabPane>

              <TabPane tab="上下文和解释" key="3">
                {result.context ? (
                  <div>
                    <Title level={5}>模式上下文</Title>
                    <div style={{ marginBottom: 16 }}>
                      <Text>此查询中使用的表：</Text>
                      <ul>
                        {result.context.schema_context?.tables.map((table: any) => (
                          <li key={table.id}>
                            <Text strong>{table.name}</Text>
                            {table.description && <Text> - {table.description}</Text>}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <Title level={5}>关系</Title>
                    <div style={{ marginBottom: 16 }}>
                      {result.context.schema_context?.relationships.length > 0 ? (
                        <ul>
                          {result.context.schema_context.relationships.map((rel: any, index: number) => (
                            <li key={index}>
                              <Text>{rel.source_table}.{rel.source_column} → {rel.target_table}.{rel.target_column}</Text>
                              {rel.relationship_type && <Text type="secondary"> ({rel.relationship_type})</Text>}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <Text>此查询中未使用关系</Text>
                      )}
                    </div>
                  </div>
                ) : (
                  <Text>无可用的上下文信息</Text>
                )}
              </TabPane>
            </Tabs>
          </div>
        )}
      </Card>
    </div>
  );
};

export default IntelligentQueryPage;
