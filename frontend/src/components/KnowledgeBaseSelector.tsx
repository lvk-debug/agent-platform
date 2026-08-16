/**
 * 知识库选择器组件
 * 选择和配置关联的知识库
 */
import React, { useState, useEffect } from 'react';
import {
  Button,
  List,
  Card,
  Switch,
  Slider,
  InputNumber,
  Typography,
  Empty,
  Modal,
  Checkbox,
  Space,
  Tag,
} from 'antd';
import { PlusOutlined, DeleteOutlined, SettingOutlined } from '@ant-design/icons';
import { KnowledgeBaseConfig } from '../services/chatbot';
import { knowledgeApi, KnowledgeBaseData } from '../services/knowledge';

const { Text, Link } = Typography;

interface KnowledgeBaseSelectorProps {
  selected: KnowledgeBaseConfig[];
  onChange: (selected: KnowledgeBaseConfig[]) => void;
}

const KnowledgeBaseSelector: React.FC<KnowledgeBaseSelectorProps> = ({
  selected,
  onChange,
}) => {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseData[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [currentKB, setCurrentKB] = useState<KnowledgeBaseConfig | null>(null);

  // 加载知识库列表
  useEffect(() => {
    fetchKnowledgeBases();
  }, []);

  const fetchKnowledgeBases = async () => {
    setLoading(true);
    try {
      const response = await knowledgeApi.getKnowledgeBases({ limit: 100 });
      setKnowledgeBases(response.data.items || []);
    } catch (error) {
      console.error('获取知识库列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 添加知识库
  const handleAdd = (kb: KnowledgeBaseData) => {
    const newConfig: KnowledgeBaseConfig = {
      knowledge_base_id: kb.id,
      name: kb.name,
      enabled: true,
      score_threshold: 0.5,
      top_k: 3,
      show_citation: false,
    };
    onChange([...selected, newConfig]);
  };

  // 移除知识库
  const handleRemove = (kbId: number) => {
    onChange(selected.filter((kb) => kb.knowledge_base_id !== kbId));
  };

  // 更新知识库配置
  const handleUpdate = (kbId: number, updates: Partial<KnowledgeBaseConfig>) => {
    onChange(
      selected.map((kb) =>
        kb.knowledge_base_id === kbId ? { ...kb, ...updates } : kb
      )
    );
  };

  // 打开设置弹窗
  const openSettings = (kb: KnowledgeBaseConfig) => {
    setCurrentKB(kb);
    setSettingsVisible(true);
  };

  // 保存设置
  const saveSettings = () => {
    if (currentKB) {
      handleUpdate(currentKB.knowledge_base_id, currentKB);
      setSettingsVisible(false);
      setCurrentKB(null);
    }
  };

  // 检查知识库是否已选择
  const isSelected = (kbId: number) =>
    selected.some((kb) => kb.knowledge_base_id === kbId);

  return (
    <div>
      <div className="mb-4 flex justify-between items-center">
        <Text strong>知识库关联</Text>
        <Button icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          添加知识库
        </Button>
      </div>

      <Text type="secondary" className="block mb-4">
        您可以导入知识库作为上下文
      </Text>

      {selected.length === 0 ? (
        <Empty description="暂未关联知识库" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          dataSource={selected}
          renderItem={(kb) => (
            <List.Item
              actions={[
                <Link onClick={() => openSettings(kb)}>
                  <SettingOutlined /> 设置
                </Link>,
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleRemove(kb.knowledge_base_id)}
                />,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text>{kb.name}</Text>
                    <Tag color={kb.enabled ? 'green' : 'default'}>
                      {kb.enabled ? '已启用' : '已禁用'}
                    </Tag>
                  </Space>
                }
                description={
                  <Space size={16}>
                    <Text type="secondary">分数阈值: {kb.score_threshold}</Text>
                    <Text type="secondary">Top K: {kb.top_k}</Text>
                    {kb.show_citation && <Tag color="blue">引用</Tag>}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      )}

      {/* 选择知识库弹窗 */}
      <Modal
        title="选择知识库"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <List
          loading={loading}
          dataSource={knowledgeBases}
          renderItem={(kb) => (
            <List.Item
              actions={[
                isSelected(kb.id) ? (
                  <Tag color="green">已选择</Tag>
                ) : (
                  <Button
                    type="primary"
                    size="small"
                    onClick={() => handleAdd(kb)}
                  >
                    添加
                  </Button>
                ),
              ]}
            >
              <List.Item.Meta
                title={kb.name}
                description={
                  <Space>
                    <Text type="secondary">文档数: {kb.document_count}</Text>
                    <Text type="secondary">分段数: {kb.chunk_count}</Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Modal>

      {/* 设置弹窗 */}
      <Modal
        title="知识库设置"
        open={settingsVisible}
        onCancel={() => {
          setSettingsVisible(false);
          setCurrentKB(null);
        }}
        onOk={saveSettings}
      >
        {currentKB && (
          <Space direction="vertical" className="w-full" size={24}>
            <div>
              <Text>启用状态</Text>
              <div>
                <Switch
                  checked={currentKB.enabled}
                  onChange={(checked) =>
                    setCurrentKB({ ...currentKB, enabled: checked })
                  }
                />
              </div>
            </div>
            <div>
              <Text>分数阈值: {currentKB.score_threshold}</Text>
              <Slider
                min={0}
                max={1}
                step={0.1}
                value={currentKB.score_threshold}
                onChange={(value) =>
                  setCurrentKB({ ...currentKB, score_threshold: value })
                }
              />
            </div>
            <div>
              <Text>Top K: {currentKB.top_k}</Text>
              <div>
                <InputNumber
                  min={1}
                  max={20}
                  value={currentKB.top_k}
                  onChange={(value) =>
                    setCurrentKB({ ...currentKB, top_k: value || 3 })
                  }
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center">
                <Text>附带引用信息</Text>
                <Switch
                  checked={currentKB.show_citation}
                  onChange={(checked) =>
                    setCurrentKB({ ...currentKB, show_citation: checked })
                  }
                />
              </div>
              <Text type="secondary" className="text-xs">
                开启后，回答中会附带来源文档名称和页码
              </Text>
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeBaseSelector;
