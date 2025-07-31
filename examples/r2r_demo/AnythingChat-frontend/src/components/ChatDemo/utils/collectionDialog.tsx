import { format, parseISO } from 'date-fns';
import { Loader } from 'lucide-react';
import { useRouter } from 'next/router';
import { CollectionResponse } from 'r2r-js';
import { useEffect, useState, useCallback } from 'react';

import { DeleteButton } from '@/components/ChatDemo/deleteButton';
import AssignDocumentToCollectionDialog from '@/components/ChatDemo/utils/AssignDocumentToCollectionDialog';
import AssignUserToCollectionDialog from '@/components/ChatDemo/utils/AssignUserToCollectionDialog';
import { Button } from '@/components/ui/Button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/use-toast';
import { useUserContext } from '@/context/UserContext';

export interface CollectionDialogProps {
  id: string;
  open: boolean;
  onClose: () => void;
}

const handleAssignSuccess = () => {
  // Do nothing
};

const formatDate = (dateString: string | undefined) => {
  if (!dateString) {
    return 'N/A';
  }
  const date = parseISO(dateString);
  return format(date, 'PPpp');
};

const formatValue = (value: any) => {
  if (value === undefined || value === null) {
    return 'N/A';
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : 'N/A';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return value.toString();
};

const CollectionDialog: React.FC<CollectionDialogProps> = ({
  id,
  open,
  onClose,
}) => {
  const [loading, setLoading] = useState(true);
  const { getClient } = useUserContext();
  const [collection, setCollection] = useState<CollectionResponse | null>(null);
  const [isPullDocumentsDialogOpen, setIsPullDocumentsDialogOpen] =
    useState(false);
  const [isAssignDocumentDialogOpen, setIsAssignDocumentDialogOpen] =
    useState(false);
  const [isAssignUserDialogOpen, setIsAssignUserDialogOpen] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const fetchCollection = useCallback(async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const collection = await client.collections.retrieve({
        id: id,
      });

      setLoading(false);

      setCollection(collection.results);
    } catch (error) {
      console.error('Error fetching document chunks:', error);
      return { results: [], totalEntries: 0 };
    }
  }, [getClient, id]);

  useEffect(() => {
    fetchCollection();
  }, [open, id, getClient, fetchCollection]);

  const handlePull = async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      client.graphs.pull({
        collectionId: id,
      });

      toast({
        variant: 'success',
        title: '拉取已触发',
        description: '提取的文档正在被拉取到图谱中',
      });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: '拉取失败',
        description: err instanceof Error ? err.message : '发生了意外错误',
      });
    }
  };

  const handleExtract = async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      client.graphs.buildCommunities({
        collectionId: id,
        runType: 'run',
      });

      toast({
        variant: 'success',
        title: '提取已开始',
        description: '提取过程已成功启动。',
      });
    } catch (err) {
      toast({
        variant: 'destructive',
        title: '提取失败',
        description: err instanceof Error ? err.message : '发生了意外错误',
      });
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="text-white max-w-4xl border border-gray-800">
          <div className="mt-4 space-y-4 h-[calc(90vh-120px)] overflow-y-auto pr-4 scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-300 -mr-4">
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold mb-4 text-gray-100">
                集合概览
              </DialogTitle>
            </DialogHeader>

            {loading ? (
              <div className="flex items-center justify-center h-64">
                <Loader className="animate-spin text-blue-500" size={64} />
              </div>
            ) : (
              <>
                {collection && (
                  <div className="grid grid-cols-1 gap-4 mb-6">
                    <InfoRow label="名称" value={collection.name} />
                    <InfoRow
                      label="描述"
                      value={collection.description}
                      isDescription={true}
                    />
                    <InfoRow label="集合ID" value={collection.id} />
                    <InfoRow
                      label="日期"
                      values={[
                        {
                          label: '创建时间',
                          value: formatDate(collection.createdAt),
                        },
                        {
                          label: '更新时间',
                          value: formatDate(collection.updatedAt),
                        },
                      ]}
                    />
                    <InfoRow label="所有者ID" value={collection.ownerId} />
                    <InfoRow
                      label="访问权限"
                      values={[
                        {
                          label: '用户数量',
                          value: collection.userCount,
                        },
                        {
                          label: '文档数量',
                          value: collection.documentCount,
                        },
                      ]}
                    />
                    <InfoRow
                      label="图谱"
                      values={[
                        {
                          label: '图谱集群状态',
                          value: collection.graphClusterStatus,
                        },
                        {
                          label: '图谱同步状态',
                          value: collection.graphSyncStatus,
                        },
                      ]}
                    />
                  </div>
                )}

                <div className="flex flex-col gap-3 mt-6 pb-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Button
                      onClick={handlePull}
                      color="primary"
                      className="font-medium py-2.5 px-4 rounded-lg"
                    >
                      将文档提取拉取到图谱
                    </Button>

                    <Button
                      onClick={handleExtract}
                      color="primary"
                      className="font-medium py-2.5 px-4 rounded-lg"
                    >
                      在图谱中提取社区
                    </Button>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <Button
                      onClick={() => setIsAssignDocumentDialogOpen(true)}
                      color="primary"
                      className="font-medium py-2.5 px-4 rounded-lg"
                    >
                      管理文件
                    </Button>

                    <Button
                      onClick={() => setIsAssignUserDialogOpen(true)}
                      color="primary"
                      className="font-medium py-2.5 px-4 rounded-lg"
                    >
                      管理用户
                    </Button>
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    <DeleteButton
                      collectionId={id}
                      isCollection={true}
                      onSuccess={() => router.push('/collections')}
                      showToast={toast}
                      selectedDocumentIds={[]}
                      onDelete={() => {}}
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <AssignDocumentToCollectionDialog
        open={isAssignDocumentDialogOpen}
        onClose={() => setIsAssignDocumentDialogOpen(false)}
        collection_id={id}
        onAssignSuccess={handleAssignSuccess}
      />
      <AssignUserToCollectionDialog
        open={isAssignUserDialogOpen}
        onClose={() => setIsAssignUserDialogOpen(false)}
        collection_id={id}
        onAssignSuccess={handleAssignSuccess}
      />
    </>
  );
};

const InfoRow: React.FC<{
  label: string;
  value?: any;
  values?: { label?: string; value: any }[];
  isDescription?: boolean;
}> = ({ label, value, values, isDescription }) => {
  const isLongContent =
    isDescription ||
    value?.length > 100 ||
    values?.some((v) => v.value?.length > 100);

  return (
    <div
      className={`py-3 border-b border-gray-700/50 ${
        isLongContent
          ? 'flex flex-col space-y-2'
          : 'flex items-center justify-between'
      }`}
    >
      <span className="font-medium text-gray-200">{label}</span>
      <div
        className={`text-gray-300 ${
          isLongContent ? 'mt-2' : 'flex items-center space-x-4'
        }`}
      >
        {value !== undefined ? (
          <span className={isDescription ? 'text-sm leading-relaxed' : ''}>
            {formatValue(value)}
          </span>
        ) : values ? (
          values.map((item, index) => (
            <span key={index} className="flex items-center">
              {item.label && (
                <span className="mr-2 text-gray-400">{item.label}:</span>
              )}
              <span>{formatValue(item.value)}</span>
            </span>
          ))
        ) : (
          'N/A'
        )}
      </div>
    </div>
  );
};

export default CollectionDialog;
