import { FileUp, PencilLine, Plus } from 'lucide-react';
import { UnprocessedChunk } from 'r2r-js/dist/types';
import React, { useState, Dispatch, SetStateAction } from 'react';

import { Button } from '@/components/ui/Button';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/popover';
import { useUserContext } from '@/context/UserContext';
import { generateIdFromLabel } from '@/lib/utils';

import { CreateDialog } from './CreateDialog';
import { UploadDialog } from './UploadDialog';

export interface UploadButtonProps {
  setUploadedDocuments: Dispatch<SetStateAction<any[]>>;
  onUploadSuccess?: () => Promise<any[]>;
  showToast?: (message: {
    title: string;
    description: string;
    variant: 'default' | 'destructive' | 'success';
  }) => void;
  setPendingDocuments?: Dispatch<SetStateAction<string[]>>;
  setCurrentPage?: React.Dispatch<React.SetStateAction<number>>;
  documentsPerPage?: number;
}

export const UploadButton: React.FC<UploadButtonProps> = ({
  setUploadedDocuments,
  onUploadSuccess,
  showToast = () => {},
  setPendingDocuments,
  setCurrentPage,
  documentsPerPage,
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [isUploadDialogOpen, setIsUploadDialogOpen] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  const { getClient } = useUserContext();

  const handleDocumentUpload = async (files: File[]) => {
    setIsUploading(true);
    const client = await getClient();
    if (!client) {
      throw new Error('Failed to get authenticated client');
    }

    const uploadedFiles: any[] = [];

    for (const file of files) {
      const fileId = generateIdFromLabel(file.name);
      uploadedFiles.push({ documentId: fileId, title: file.name });

      client.documents
        .create({
          file: file,
        })
        .catch((err) => {
          showToast({
            variant: 'destructive',
            title: '上传失败',
            description: err instanceof Error ? err.message : '发生了意外错误',
          });
        });
    }

    setUploadedDocuments((prevDocuments) => [
      ...prevDocuments,
      ...uploadedFiles,
    ]);

    if (setPendingDocuments) {
      const newUploadedFiles = uploadedFiles.map((file) => file.documentId);
      setPendingDocuments((prev) => [...prev, ...newUploadedFiles]);
    }

    showToast({
      variant: 'success',
      title: '上传已开始',
      description: '文件正在后台上传中。',
    });

    if (onUploadSuccess) {
      onUploadSuccess().then((updatedDocuments) => {
        if (updatedDocuments.length > 0 && setCurrentPage && documentsPerPage) {
          const totalPages = Math.ceil(
            updatedDocuments.length / documentsPerPage
          );
          setCurrentPage(1);
        } else if (setCurrentPage) {
          setCurrentPage(1);
        }
      });
    }

    setIsUploading(false);
  };

  const handleCreateChunks = async (
    chunks: UnprocessedChunk[],
    documentId?: string,
    metadata?: Record<string, any>
  ) => {
    const client = await getClient();
    if (!client) {
      throw new Error('Failed to get authenticated client');
    }

    const processedChunks = chunks.map((chunk) => ({
      ...chunk,
      documentId: documentId || chunk.documentId,
      metadata: { ...chunk.metadata, ...metadata },
    }));

    client.chunks
      .create({
        chunks: processedChunks,
      })
      .catch((error) => {
        showToast({
          variant: 'destructive',
          title: '创建失败',
          description:
            error instanceof Error ? error.message : '发生了意外错误',
        });
      });

    showToast({
      variant: 'success',
      title: '片段创建已开始',
      description: '片段正在后台创建中。',
    });

    if (onUploadSuccess) {
      onUploadSuccess();
    }
  };

  return (
    <>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            className="pl-2 pr-2 py-2 px-4"
            color="filled"
            shape="rounded"
            disabled={isUploading}
            style={{ zIndex: 20, minWidth: '100px' }}
          >
            <Plus className="mr-2 h-4 w-4 mt-1" />
            {isUploading ? '上传中...' : '新建'}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[150px] p-1">
          <div className="flex flex-col gap-1">
            <Button
              onClick={() => setIsUploadDialogOpen(true)}
              color="secondary"
              className="flex justify-between items-center"
            >
              <FileUp className="mr-2 h-4 w-4" />
              <span>文件上传</span>
            </Button>
            <Button
              onClick={() => setIsCreateDialogOpen(true)}
              color="secondary"
              className="flex justify-between items-center"
            >
              <PencilLine className="mr-2 h-4 w-4" />
              <span>创建片段</span>
            </Button>
          </div>
        </PopoverContent>
      </Popover>
      <UploadDialog
        isOpen={isUploadDialogOpen}
        onClose={() => setIsUploadDialogOpen(false)}
        onUpload={handleDocumentUpload}
      />
      <CreateDialog
        isOpen={isCreateDialogOpen}
        onClose={() => setIsCreateDialogOpen(false)}
        onCreateChunks={handleCreateChunks}
      />
    </>
  );
};
