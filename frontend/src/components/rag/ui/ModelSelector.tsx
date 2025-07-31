import React, { useState, useEffect } from 'react';
import { Select, Modal, Input, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useRAGContext } from '@/contexts/RAGContext';

const { Option } = Select;

interface ModelSelectorProps {
  id?: string;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
}

const predefinedModels = [
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
  { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
  { value: 'ollama/llama3.1', label: 'Ollama Llama 3.1' },
  { value: 'ollama/qwen2', label: 'Ollama Qwen2' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
];

const ModelSelector: React.FC<ModelSelectorProps> = ({
  id,
  className = '',
  placeholder = '选择模型',
  disabled = false
}) => {
  const { selectedModel, setSelectedModel } = useRAGContext();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [customModelValue, setCustomModelValue] = useState('');
  const [allModels, setAllModels] = useState(predefinedModels);

  useEffect(() => {
    // 从localStorage加载自定义模型
    const savedCustomModels = localStorage.getItem('rag_custom_models');
    if (savedCustomModels) {
      try {
        const customModels = JSON.parse(savedCustomModels);
        setAllModels(prev => [...prev, ...customModels]);
      } catch (error) {
        console.error('Failed to load custom models:', error);
      }
    }
  }, []);

  const handleSelectChange = (value: string) => {
    if (value === 'add_custom') {
      setIsModalOpen(true);
    } else {
      setSelectedModel(value);
    }
  };

  const handleCustomModelSubmit = () => {
    if (customModelValue.trim()) {
      const trimmedValue = customModelValue.trim();
      const newModel = { value: trimmedValue, label: trimmedValue };

      // 检查是否已存在
      const exists = allModels.some(model => model.value === trimmedValue);
      if (exists) {
        Modal.warning({
          title: '模型已存在',
          content: '该模型已经在列表中了',
        });
        return;
      }

      // 添加到列表
      const updatedModels = [...allModels, newModel];
      setAllModels(updatedModels);

      // 保存自定义模型到localStorage
      const customModels = updatedModels.filter(model =>
        !predefinedModels.some(predefined => predefined.value === model.value)
      );
      localStorage.setItem('rag_custom_models', JSON.stringify(customModels));

      // 选择新添加的模型
      setSelectedModel(trimmedValue);

      // 关闭弹窗并重置输入
      setCustomModelValue('');
      setIsModalOpen(false);
    }
  };

  const handleModalCancel = () => {
    setCustomModelValue('');
    setIsModalOpen(false);
  };

  const removeCustomModel = (modelValue: string) => {
    // 只能删除自定义模型，不能删除预定义模型
    const isPredefined = predefinedModels.some(model => model.value === modelValue);
    if (isPredefined) {
      return;
    }

    const updatedModels = allModels.filter(model => model.value !== modelValue);
    setAllModels(updatedModels);

    // 更新localStorage
    const customModels = updatedModels.filter(model =>
      !predefinedModels.some(predefined => predefined.value === model.value)
    );
    localStorage.setItem('rag_custom_models', JSON.stringify(customModels));

    // 如果删除的是当前选中的模型，重置选择
    if (selectedModel === modelValue) {
      setSelectedModel('');
    }
  };

  return (
    <div id={id} className={className}>
      <Select
        value={selectedModel}
        onChange={handleSelectChange}
        placeholder={placeholder}
        disabled={disabled}
        style={{ width: '100%' }}
        showSearch
        filterOption={(input, option) =>
          (option?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
        }
        dropdownRender={(menu) => (
          <div>
            {menu}
            <div style={{ padding: '8px 0', borderTop: '1px solid #f0f0f0' }}>
              <Button
                type="text"
                icon={<PlusOutlined />}
                onClick={() => setIsModalOpen(true)}
                style={{ width: '100%', textAlign: 'left' }}
              >
                添加自定义模型
              </Button>
            </div>
          </div>
        )}
      >
        {allModels.map((model) => {
          const isCustom = !predefinedModels.some(predefined => predefined.value === model.value);
          return (
            <Option key={model.value} value={model.value}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{model.label}</span>
                {isCustom && (
                  <Button
                    type="text"
                    size="small"
                    danger
                    onClick={(e) => {
                      e.stopPropagation();
                      removeCustomModel(model.value);
                    }}
                    style={{ padding: '0 4px', fontSize: '12px' }}
                  >
                    删除
                  </Button>
                )}
              </div>
            </Option>
          );
        })}
      </Select>

      <Modal
        title="添加自定义模型"
        open={isModalOpen}
        onOk={handleCustomModelSubmit}
        onCancel={handleModalCancel}
        okText="添加"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ margin: '16px 0' }}>
          <Input
            value={customModelValue}
            onChange={(e) => setCustomModelValue(e.target.value)}
            placeholder="输入模型名称，例如：gpt-4, claude-3-opus"
            onPressEnter={handleCustomModelSubmit}
            autoFocus
          />
          <div style={{ marginTop: 8, fontSize: '12px', color: '#666' }}>
            支持的格式：
            <br />
            • OpenAI: gpt-4, gpt-3.5-turbo
            <br />
            • Anthropic: claude-3-opus, claude-3-sonnet
            <br />
            • Ollama: ollama/llama3.1, ollama/qwen2
            <br />
            • 其他: deepseek-chat, moonshot-v1-8k
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default ModelSelector;
