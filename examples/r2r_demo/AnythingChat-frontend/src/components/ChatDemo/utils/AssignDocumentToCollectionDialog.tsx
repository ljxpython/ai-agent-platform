import { Loader } from 'lucide-react';
import { DocumentResponse } from 'r2r-js';
import React, { useState, useEffect, useCallback } from 'react';

import DocumentsTable from '@/components/ChatDemo/DocumentsTable';
import { Button } from '@/components/ui/Button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/use-toast';
import { useUserContext } from '@/context/UserContext';

interface AssignDocumentToCollectionDialogProps {
  open: boolean;
  onClose: () => void;
  collection_id: string;
  onAssignSuccess: () => void;
}

const AssignDocumentToCollectionDialog: React.FC<
  AssignDocumentToCollectionDialogProps
> = ({ open, onClose, collection_id, onAssignSuccess }) => {
  const { getClient } = useUserContext();
  const { toast } = useToast();

  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingDocuments, setPendingDocuments] = useState<string[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [assigning, setAssigning] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(
    {}
  );

  const [filters, setFilters] = useState<Record<string, any>>({});
  const [searchQuery, setSearchQuery] = useState('');

  const handleToggleColumn = useCallback(
    (columnKey: string, isVisible: boolean) => {
      setVisibleColumns((prev) => ({ ...prev, [columnKey]: isVisible }));
    },
    []
  );

  const fetchAllDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      let allDocuments: DocumentResponse[] = [];
      let offset = 0;
      const limit = 100;
      let totalEntries = 0;

      do {
        const data = await client.documents.list({
          offset: offset,
          limit: limit,
        });
        totalEntries = data.totalEntries;
        allDocuments = allDocuments.concat(data.results);
        offset += limit;
      } while (allDocuments.length < totalEntries);

      // Filter out documents that are already in the collection
      const filteredDocs = allDocuments.filter(
        (doc) => !doc.collectionIds.includes(collection_id)
      );

      setDocuments(filteredDocs);
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch documents. Please try again later.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [getClient, toast, collection_id]);

  useEffect(() => {
    if (open) {
      fetchAllDocuments();
      setSelectedDocumentIds([]);
      const initialVisibility: Record<string, boolean> = {
        title: true,
        id: true,
        userId: true,
        ingestionStatus: true,
        createdAt: true,
      };
      setVisibleColumns(initialVisibility);
    }
  }, [open, fetchAllDocuments]);

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setSelectedDocumentIds(documents.map((doc) => doc.id));
    } else {
      setSelectedDocumentIds([]);
    }
  };

  const handleSelectItem = (itemId: string, selected: boolean) => {
    if (selected) {
      setSelectedDocumentIds((prev) => [...prev, itemId]);
    } else {
      setSelectedDocumentIds((prev) => prev.filter((id) => id !== itemId));
    }
  };

  const handleAssign = async () => {
    if (selectedDocumentIds.length === 0) {
      toast({
        title: '未选择文档',
        description: '请至少选择一个文档进行分配。',
        variant: 'destructive',
      });
      return;
    }

    setAssigning(true);
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const assignPromises = selectedDocumentIds.map((docId) =>
        client.collections.addDocument({
          id: collection_id,
          documentId: docId,
        })
      );

      await Promise.all(assignPromises);

      toast({
        title: '成功',
        description: '选中的文档已分配到集合。',
        variant: 'success',
      });

      onAssignSuccess();
      onClose();
    } catch (error) {
      console.error('Error assigning documents:', error);
      toast({
        title: '错误',
        description: '分配文档失败，请稍后重试。',
        variant: 'destructive',
      });
    } finally {
      setAssigning(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="text-white max-w-4xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold mb-4">
            分配文档到集合
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center items-center mt-20">
            <Loader className="animate-spin" size={64} />
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-4">所有文档已分配到此集合。</div>
        ) : (
          <>
            <DocumentsTable
              documents={documents}
              loading={false}
              onRefresh={fetchAllDocuments}
              pendingDocuments={pendingDocuments}
              setPendingDocuments={setPendingDocuments}
              onSelectAll={handleSelectAll}
              onSelectItem={handleSelectItem}
              selectedItems={selectedDocumentIds}
              showPagination={false}
              hideActions={true}
              visibleColumns={visibleColumns}
              onToggleColumn={handleToggleColumn}
              itemsPerPage={10}
              filters={filters}
              onFiltersChange={setFilters}
              searchQuery={searchQuery}
              onSearchQueryChange={setSearchQuery}
            />
            <DialogFooter className="mt-4 flex justify-end space-x-2">
              <Button
                onClick={handleAssign}
                color="filled"
                disabled={assigning || selectedDocumentIds.length === 0}
                style={{ zIndex: 20 }}
              >
                分配到集合
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AssignDocumentToCollectionDialog;
