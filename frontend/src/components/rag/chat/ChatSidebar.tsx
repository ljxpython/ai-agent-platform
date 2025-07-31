import React from 'react';
import {
  Card,
  Switch,
  Slider,
  InputNumber,
  Select,
  Checkbox,
  Space,
  Typography,
  Collapse,
  Row,
  Col
} from 'antd';
import {
  SearchOutlined,
  SettingOutlined,
  MessageOutlined
} from '@ant-design/icons';
import { SidebarProps } from '@/types/rag';
import ModelSelector from '../ui/ModelSelector';

const { Text } = Typography;
const { Option } = Select;
const { Panel } = Collapse;

const ChatSidebar: React.FC<SidebarProps> = ({
  // isOpen,
  // onToggle,
  switches,
  handleSwitchChange,
  searchLimit,
  setSearchLimit,
  // searchFilters,
  // setSearchFilters,
  collections,
  selectedCollectionIds,
  setSelectedCollectionIds,
  indexMeasure,
  setIndexMeasure,
  includeMetadatas,
  setIncludeMetadatas,
  probes,
  setProbes,
  efSearch,
  setEfSearch,
  fullTextWeight,
  setFullTextWeight,
  semanticWeight,
  setSemanticWeight,
  // fullTextLimit,
  // setFullTextLimit,
  // rrfK,
  // setRrfK,
  // kgSearchLevel,
  // setKgSearchLevel,
  // maxCommunityDescriptionLength,
  // setMaxCommunityDescriptionLength,
  // localSearchLimits,
  // setLocalSearchLimits,
  temperature,
  setTemperature,
  topP,
  setTopP,
  topK,
  setTopK,
  maxTokensToSample,
  setMaxTokensToSample,
  config,
  // onConversationSelect,
}) => {
  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <Collapse
        defaultActiveKey={['search', 'generation']}
        ghost
        size="small"
      >
        {/* 搜索配置 */}
        <Panel
          header={
            <Space>
              <SearchOutlined />
              <span>搜索配置</span>
            </Space>
          }
          key="search"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {/* 搜索开关 */}
            <Card size="small" title="搜索方式">
              <Space direction="vertical" style={{ width: '100%' }}>
                {switches.vectorSearch && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text>向量搜索</Text>
                    <Switch
                      checked={switches.vectorSearch.checked}
                      onChange={(checked) => handleSwitchChange('vectorSearch', checked)}
                      size="small"
                    />
                  </div>
                )}

                {switches.hybridSearch && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text>混合搜索</Text>
                    <Switch
                      checked={switches.hybridSearch.checked}
                      onChange={(checked) => handleSwitchChange('hybridSearch', checked)}
                      size="small"
                    />
                  </div>
                )}

                {switches.knowledgeGraphSearch && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text>知识图谱搜索</Text>
                    <Switch
                      checked={switches.knowledgeGraphSearch.checked}
                      onChange={(checked) => handleSwitchChange('knowledgeGraphSearch', checked)}
                      size="small"
                    />
                  </div>
                )}
              </Space>
            </Card>

            {/* 基础搜索参数 */}
            <Card size="small" title="基础参数">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text>搜索限制</Text>
                  <Row gutter={8} style={{ marginTop: 4 }}>
                    <Col span={16}>
                      <Slider
                        min={1}
                        max={50}
                        value={searchLimit}
                        onChange={setSearchLimit}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={1}
                        max={50}
                        value={searchLimit}
                        onChange={(value) => setSearchLimit(value || 10)}
                        size="small"
                        style={{ width: '100%' }}
                      />
                    </Col>
                  </Row>
                </div>

                <div>
                  <Text>索引度量</Text>
                  <Select
                    value={indexMeasure}
                    onChange={setIndexMeasure}
                    style={{ width: '100%', marginTop: 4 }}
                    size="small"
                  >
                    <Option value="cosine_distance">余弦距离</Option>
                    <Option value="l2_distance">L2距离</Option>
                    <Option value="max_inner_product">最大内积</Option>
                  </Select>
                </div>

                <div>
                  <Checkbox
                    checked={includeMetadatas}
                    onChange={(e) => setIncludeMetadatas(e.target.checked)}
                  >
                    包含元数据
                  </Checkbox>
                </div>
              </Space>
            </Card>

            {/* 集合选择 */}
            <Card size="small" title="知识库集合">
              <Select
                mode="multiple"
                placeholder="选择集合"
                value={selectedCollectionIds}
                onChange={setSelectedCollectionIds}
                style={{ width: '100%' }}
                size="small"
                allowClear
              >
                {collections.map((collection) => (
                  <Option key={collection.id} value={collection.id}>
                    {collection.name}
                  </Option>
                ))}
              </Select>
            </Card>

            {/* 高级搜索参数 */}
            {(switches.vectorSearch?.checked || switches.hybridSearch?.checked) && (
              <Card size="small" title="高级参数">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {probes !== undefined && (
                    <div>
                      <Text>探针数量</Text>
                      <InputNumber
                        min={1}
                        max={1000}
                        value={probes}
                        onChange={(value) => setProbes?.(value || 1)}
                        style={{ width: '100%', marginTop: 4 }}
                        size="small"
                      />
                    </div>
                  )}

                  {efSearch !== undefined && (
                    <div>
                      <Text>EF搜索</Text>
                      <InputNumber
                        min={1}
                        max={1000}
                        value={efSearch}
                        onChange={(value) => setEfSearch?.(value || 1)}
                        style={{ width: '100%', marginTop: 4 }}
                        size="small"
                      />
                    </div>
                  )}
                </Space>
              </Card>
            )}

            {/* 混合搜索参数 */}
            {switches.hybridSearch?.checked && (
              <Card size="small" title="混合搜索参数">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <Text>全文权重</Text>
                    <Row gutter={8} style={{ marginTop: 4 }}>
                      <Col span={16}>
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          value={fullTextWeight}
                          onChange={setFullTextWeight}
                        />
                      </Col>
                      <Col span={8}>
                        <InputNumber
                          min={0}
                          max={1}
                          step={0.1}
                          value={fullTextWeight}
                          onChange={(value) => setFullTextWeight?.(value || 0)}
                          size="small"
                          style={{ width: '100%' }}
                        />
                      </Col>
                    </Row>
                  </div>

                  <div>
                    <Text>语义权重</Text>
                    <Row gutter={8} style={{ marginTop: 4 }}>
                      <Col span={16}>
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          value={semanticWeight}
                          onChange={setSemanticWeight}
                        />
                      </Col>
                      <Col span={8}>
                        <InputNumber
                          min={0}
                          max={1}
                          step={0.1}
                          value={semanticWeight}
                          onChange={(value) => setSemanticWeight?.(value || 0)}
                          size="small"
                          style={{ width: '100%' }}
                        />
                      </Col>
                    </Row>
                  </div>
                </Space>
              </Card>
            )}
          </Space>
        </Panel>

        {/* 生成配置 */}
        <Panel
          header={
            <Space>
              <SettingOutlined />
              <span>生成配置</span>
            </Space>
          }
          key="generation"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {/* 模型选择 */}
            <Card size="small" title="模型设置">
              <ModelSelector />
            </Card>

            {/* 生成参数 */}
            <Card size="small" title="生成参数">
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text>温度 (Temperature)</Text>
                  <Row gutter={8} style={{ marginTop: 4 }}>
                    <Col span={16}>
                      <Slider
                        min={0}
                        max={2}
                        step={0.1}
                        value={temperature}
                        onChange={setTemperature}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={0}
                        max={2}
                        step={0.1}
                        value={temperature}
                        onChange={(value) => setTemperature?.(value || 0)}
                        size="small"
                        style={{ width: '100%' }}
                      />
                    </Col>
                  </Row>
                </div>

                <div>
                  <Text>Top P</Text>
                  <Row gutter={8} style={{ marginTop: 4 }}>
                    <Col span={16}>
                      <Slider
                        min={0}
                        max={1}
                        step={0.1}
                        value={topP}
                        onChange={setTopP}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={0}
                        max={1}
                        step={0.1}
                        value={topP}
                        onChange={(value) => setTopP?.(value || 0)}
                        size="small"
                        style={{ width: '100%' }}
                      />
                    </Col>
                  </Row>
                </div>

                <div>
                  <Text>Top K</Text>
                  <Row gutter={8} style={{ marginTop: 4 }}>
                    <Col span={16}>
                      <Slider
                        min={1}
                        max={200}
                        value={topK}
                        onChange={setTopK}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={1}
                        max={200}
                        value={topK}
                        onChange={(value) => setTopK?.(value || 0)}
                        size="small"
                        style={{ width: '100%' }}
                      />
                    </Col>
                  </Row>
                </div>

                <div>
                  <Text>最大令牌数</Text>
                  <Row gutter={8} style={{ marginTop: 4 }}>
                    <Col span={16}>
                      <Slider
                        min={100}
                        max={4000}
                        step={100}
                        value={maxTokensToSample}
                        onChange={setMaxTokensToSample}
                      />
                    </Col>
                    <Col span={8}>
                      <InputNumber
                        min={100}
                        max={4000}
                        step={100}
                        value={maxTokensToSample}
                        onChange={(value) => setMaxTokensToSample?.(value || 0)}
                        size="small"
                        style={{ width: '100%' }}
                      />
                    </Col>
                  </Row>
                </div>
              </Space>
            </Card>
          </Space>
        </Panel>

        {/* 对话历史 */}
        {config.showConversations && (
          <Panel
            header={
              <Space>
                <MessageOutlined />
                <span>对话历史</span>
              </Space>
            }
            key="conversations"
          >
            <Card size="small">
              <Text type="secondary">对话历史功能正在开发中...</Text>
            </Card>
          </Panel>
        )}
      </Collapse>
    </div>
  );
};

export default ChatSidebar;
