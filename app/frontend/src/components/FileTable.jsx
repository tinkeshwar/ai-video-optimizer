import React, { useEffect, useState, useCallback } from 'react';
import { Flex, Button, Table, Box, Tooltip, Progress, Spinner, Text, Checkbox } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon, InfoCircledIcon, ResetIcon, TrashIcon, ChevronUpIcon, ChevronDownIcon, CodeIcon, CountdownTimerIcon, Pencil2Icon } from '@radix-ui/react-icons';
import axios from 'axios';
import Filters from './Filter';
import ConfirmDialog from './ConfirmDialog';
import HistoryDialog from './HistoryDialog';
import CommandEditDialog from './CommandEditDialog';
import { useToast } from './Toast';
import { byteToHuman, runtimeFromProbe, compressionPercent, progressFromProbe, relativeTime } from '../helpers';

const ACTION_CONFIG = {
  pending: { positive: 'confirmed', negative: 'rejected', delete: true },
  confirmed: { revert: 'pending' },
  optimized: { positive: 'accepted', negative: 'skipped' },
  ready: { revert: 'pending' },
  rejected: { delete: true },
  skipped: { delete: true },
  failed: { delete: true },
};

const DESTRUCTIVE = new Set(['rejected', 'skipped', 'delete']);

function FileTable({ status, onAction }) {
  const toast = useToast();
  const [files, setFiles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all');
  const [codecFilter, setCodecFilter] = useState('all');
  const [fileNameSearch, setFileNameSearch] = useState('');
  const [filePathSearch, setFilePathSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [sortBy, setSortBy] = useState(null);
  const [sortOrder, setSortOrder] = useState('asc');
  const [expandedId, setExpandedId] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [historyModal, setHistoryModal] = useState(null);
  const [commandModal, setCommandModal] = useState(null);
  const itemsPerPage = 50;

  const HISTORY_TABS = new Set(['confirmed', 'ready', 'processing', 'optimized', 'replaced', 'rejected', 'skipped', 'failed']);
  const COMMAND_EDIT_TABS = new Set(['confirmed', 'ready', 'processing', 'optimized', 'skipped', 'failed']);
  const hasActions = Object.keys(ACTION_CONFIG).includes(status);
  const showHistory = HISTORY_TABS.has(status);
  const showCommandEdit = COMMAND_EDIT_TABS.has(status);

  const toByte = (size) => {
    if (size === 'all') return null;
    const multiplier = size.endsWith('GB') ? 1e9 : size.endsWith('MB') ? 1e6 : 1;
    return parseFloat(size) * multiplier;
  };

  const toCodec = useCallback((codec) => (codec === 'all' ? null : codec.toLowerCase()), []);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`/api/videos/${status}`, {
        params: {
          page: currentPage, limit: itemsPerPage,
          size: toByte(sizeFilter), codec: toCodec(codecFilter),
          name: fileNameSearch, directory: filePathSearch,
          sort_by: sortBy, sort_order: sortOrder,
        },
      });
      setFiles(response.data.list);
      setTotalPages(response.data.total_pages);
      setSelected(new Set());
    } catch (err) {
      if (!axios.isCancel(err)) setError('Failed to fetch files.');
    } finally {
      setLoading(false);
    }
  }, [currentPage, sizeFilter, codecFilter, fileNameSearch, filePathSearch, sortBy, sortOrder, status, toCodec]);

  useEffect(() => {
    const timer = setTimeout(fetchFiles, 300);
    return () => clearTimeout(timer);
  }, [fetchFiles]);

  useEffect(() => {
    if (['ready', 'processing', 'pending', 'confirmed', 'optimized'].includes(status)) {
      const interval = setInterval(fetchFiles, 10000);
      return () => clearInterval(interval);
    }
  }, [status, fetchFiles]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setSortOrder('asc');
    }
  };

  const SortIcon = ({ col }) => {
    if (sortBy !== col) return null;
    return sortOrder === 'asc' ? <ChevronUpIcon /> : <ChevronDownIcon />;
  };

  const handleAction = async (id, action) => {
    try {
      const endpoint = action === 'delete' ? `/api/videos/${id}` : `/api/videos/${id}/status`;
      const method = action === 'delete' ? 'delete' : 'post';
      const data = action !== 'delete' ? { status: action } : undefined;
      await axios({ method, url: endpoint, data });
      toast(`Action "${action}" completed`, 'success');
      fetchFiles();
      onAction?.();
    } catch (err) {
      toast(`Action "${action}" failed`, 'error');
    }
  };

  const handleBulkAction = async (action) => {
    const ids = [...selected];
    if (!ids.length) return;
    try {
      if (action === 'delete') {
        await Promise.all(ids.map((id) => axios.delete(`/api/videos/${id}`)));
      } else {
        await axios.post('/api/videos/status', { video_ids: ids, status: action });
      }
      toast(`Bulk "${action}" completed for ${ids.length} videos`, 'success');
      fetchFiles();
      onAction?.();
    } catch (err) {
      toast(`Bulk action failed`, 'error');
    }
  };

  const confirmAction = (id, action) => {
    if (DESTRUCTIVE.has(action)) {
      setConfirm({ id, action, message: `Are you sure you want to ${action === 'delete' ? 'delete' : action} this video?` });
    } else {
      handleAction(id, action);
    }
  };

  const confirmBulk = (action) => {
    if (DESTRUCTIVE.has(action)) {
      setConfirm({ bulk: true, action, message: `Are you sure you want to ${action} ${selected.size} video(s)?` });
    } else {
      handleBulkAction(action);
    }
  };

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === files.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(files.map((f) => f.id)));
    }
  };

  const countAttempts = (history) => {
    if (!history) return 0;
    return history.filter((h) => ['confirmed', 're-confirmed'].includes(h.status)).length;
  };

  const config = ACTION_CONFIG[status];

  if (!loading && !error && files.length === 0) {
    return (
      <>
        <Box p="4" style={{ borderBottom: '1px solid var(--header-border)', backgroundColor: 'var(--filter-bg)' }}>
          <Filters
            sizeFilter={sizeFilter} setSizeFilter={setSizeFilter}
            codecFilter={codecFilter} setCodecFilter={setCodecFilter}
            fileNameSearch={fileNameSearch} setFileNameSearch={setFileNameSearch}
            filePathSearch={filePathSearch} setFilePathSearch={setFilePathSearch}
          />
        </Box>
        <Flex direction="column" align="center" justify="center" py="9" gap="2">
          <Text size="6">📭</Text>
          <Text size="3" color="gray">No videos in this category</Text>
        </Flex>
      </>
    );
  }

  return (
    <>
      <Box p="4" style={{ borderBottom: '1px solid var(--header-border)', backgroundColor: 'var(--filter-bg)', position: 'sticky', top: 92, zIndex: 98 }}>
        <Filters
          sizeFilter={sizeFilter} setSizeFilter={setSizeFilter}
          codecFilter={codecFilter} setCodecFilter={setCodecFilter}
          fileNameSearch={fileNameSearch} setFileNameSearch={setFileNameSearch}
          filePathSearch={filePathSearch} setFilePathSearch={setFilePathSearch}
        />
        {hasActions && selected.size > 0 && (
          <Flex gap="2" mt="2" align="center">
            <Text size="1" color="gray">{selected.size} selected</Text>
            {config?.positive && <Button size="1" color="green" onClick={() => confirmBulk(config.positive)}><CheckIcon /> {config.positive}</Button>}
            {config?.negative && <Button size="1" color="yellow" onClick={() => confirmBulk(config.negative)}><Cross2Icon /> {config.negative}</Button>}
            {config?.revert && <Button size="1" color="blue" onClick={() => confirmBulk(config.revert)}><ResetIcon /> Revert</Button>}
            {config?.delete && <Button size="1" color="red" onClick={() => confirmBulk('delete')}><TrashIcon /> Delete</Button>}
          </Flex>
        )}
      </Box>

      {loading ? (
        <Flex justify="center" mt="4"><Spinner size="3" /></Flex>
      ) : error ? (
        <Flex justify="center" mt="4"><Text color="red">{error}</Text></Flex>
      ) : (
        <Table.Root size="1" variant="surface">
          <Table.Header>
            <Table.Row>
              {hasActions && (
                <Table.ColumnHeaderCell style={{ width: 32 }}>
                  <Checkbox checked={selected.size === files.length && files.length > 0} onCheckedChange={toggleAll} />
                </Table.ColumnHeaderCell>
              )}
              <Table.ColumnHeaderCell onClick={() => handleSort('filename')} style={{ cursor: 'pointer' }}>
                <Flex align="center" gap="1">Name <SortIcon col="filename" /></Flex>
              </Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell onClick={() => handleSort('original_codec')} style={{ cursor: 'pointer' }}>
                <Flex align="center" gap="1">Codec <SortIcon col="original_codec" /></Flex>
              </Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Runtime</Table.ColumnHeaderCell>
              {status === 'optimized' && <Table.ColumnHeaderCell>Compressed</Table.ColumnHeaderCell>}
              {(status === 'optimized' || status === 'failed') && <Table.ColumnHeaderCell>Attempts</Table.ColumnHeaderCell>}
              <Table.ColumnHeaderCell onClick={() => handleSort('original_size')} style={{ cursor: 'pointer' }}>
                <Flex align="center" gap="1">Size <SortIcon col="original_size" /></Flex>
              </Table.ColumnHeaderCell>
              {(status === 'ready' || status === 'processing') && <Table.ColumnHeaderCell>Progress</Table.ColumnHeaderCell>}
              <Table.ColumnHeaderCell onClick={() => handleSort('updated_at')} style={{ cursor: 'pointer' }}>
                <Flex align="center" gap="1">Updated <SortIcon col="updated_at" /></Flex>
              </Table.ColumnHeaderCell>
              {(hasActions || showHistory || showCommandEdit) && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {files.map((file, index) => (
              <React.Fragment key={file.id}>
                <Table.Row style={{ backgroundColor: index % 2 === 0 ? 'var(--row-alt-bg)' : 'transparent' }}>
                  {hasActions && (
                    <Table.Cell>
                      <Checkbox checked={selected.has(file.id)} onCheckedChange={() => toggleSelect(file.id)} />
                    </Table.Cell>
                  )}
                  <Table.Cell>
                    <Flex align="center" gap="1">
                      {file.filename}
                      <Tooltip content={file.filepath}><InfoCircledIcon /></Tooltip>
                      {(file.ai_command || file.ffprobe_data) && ['ready', 'processing', 'optimized', 'replaced', 'failed', 'confirmed', 'skipped'].includes(status) && (
                        <Tooltip content="View AI command">
                          <Button size="1" variant="ghost" onClick={() => setExpandedId(expandedId === file.id ? null : file.id)}>
                            <CodeIcon />
                          </Button>
                        </Tooltip>
                      )}
                    </Flex>
                  </Table.Cell>
                  <Table.Cell>
                    {file.original_codec}
                    {file.new_codec && ` → ${file.new_codec}`}
                  </Table.Cell>
                  <Table.Cell>{file.ffprobe_data ? runtimeFromProbe(file.ffprobe_data) : 'NA'}</Table.Cell>
                  {status === 'optimized' && <Table.Cell>{compressionPercent(file.original_size, file.optimized_size)}</Table.Cell>}
                  {(status === 'optimized' || status === 'failed') && <Table.Cell>{countAttempts(file?.history)}</Table.Cell>}
                  <Table.Cell>
                    {byteToHuman(Number(file.original_size))}
                    {file.optimized_size && ` → ${byteToHuman(Number(file.optimized_size))}`}
                  </Table.Cell>
                  {(status === 'ready' || status === 'processing') && (
                    <Table.Cell>
                      {(() => {
                        const p = progressFromProbe(file.ffprobe_data, file.progress);
                        return (
                          <Flex direction="column" gap="1">
                            <Flex align="center" gap="2">
                              <Progress size="3" value={p.percent} variant="classic" style={{ flex: 1 }} />
                              <Text size="1" weight="bold">{p.percent}%</Text>
                            </Flex>
                            <Text size="1" color="gray">ETA: {p.eta} · {p.size} · {p.processed} · {p.speed}</Text>
                          </Flex>
                        );
                      })()}
                    </Table.Cell>
                  )}
                  <Table.Cell>
                    <Tooltip content={file.updated_at || file.created_at || ''}>
                      <Text size="1" color="gray">{relativeTime(file.updated_at || file.created_at)}</Text>
                    </Tooltip>
                  </Table.Cell>
                  {(hasActions || showHistory || showCommandEdit) && (
                    <Table.Cell>
                      <Flex gap="2">
                        {config?.positive && (
                          <Button size="1" color="green" onClick={() => confirmAction(file.id, config.positive)}><CheckIcon /></Button>
                        )}
                        {config?.negative && (
                          <Button size="1" color="yellow" onClick={() => confirmAction(file.id, config.negative)}><Cross2Icon /></Button>
                        )}
                        {config?.revert && (
                          <Button size="1" color="blue" onClick={() => handleAction(file.id, config.revert)}><ResetIcon /></Button>
                        )}
                        {config?.delete && (
                          <Button size="1" color="red" onClick={() => confirmAction(file.id, 'delete')}><TrashIcon /></Button>
                        )}
                        {showCommandEdit && (
                          <Tooltip content="Edit command & queue">
                            <Button size="1" variant="soft" color="indigo" onClick={() => setCommandModal(file)}><Pencil2Icon /></Button>
                          </Tooltip>
                        )}
                        {showHistory && (
                          <Tooltip content="View history">
                            <Button size="1" variant="soft" color="gray" onClick={() => setHistoryModal(file)}><CountdownTimerIcon /></Button>
                          </Tooltip>
                        )}
                      </Flex>
                    </Table.Cell>
                  )}
                </Table.Row>
                {expandedId === file.id && (
                  <Table.Row>
                    <Table.Cell colSpan={10} style={{ background: 'var(--expanded-bg)', padding: '12px 16px' }}>
                      <Flex gap="4" wrap="wrap">
                        {file.ffprobe_data && (
                          <Box style={{ flex: 1, minWidth: 280 }}>
                            <Flex justify="between" align="center" mb="1">
                              <Text size="1" color="gray" weight="bold">📋 Metadata</Text>
                              <Button size="1" variant="ghost" onClick={() => { navigator.clipboard.writeText(JSON.stringify(JSON.parse(file.ffprobe_data), null, 2)); toast('Metadata copied', 'info'); }}>Copy</Button>
                            </Flex>
                            <pre style={{ margin: 0, padding: 8, background: 'var(--code-bg)', borderRadius: 6, fontSize: 11, fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 240, overflow: 'auto', cursor: 'text', userSelect: 'text' }}>
                              {JSON.stringify(JSON.parse(file.ffprobe_data), null, 2)}
                            </pre>
                          </Box>
                        )}
                        {file.ai_command && (
                          <Box style={{ flex: 1, minWidth: 280 }}>
                            <Flex justify="between" align="center" mb="1">
                              <Text size="1" color="gray" weight="bold">🤖 AI Command</Text>
                              <Button size="1" variant="ghost" onClick={() => { navigator.clipboard.writeText(file.ai_command); toast('Command copied', 'info'); }}>Copy</Button>
                            </Flex>
                            <pre style={{ margin: 0, padding: 8, background: 'var(--code-bg)', borderRadius: 6, fontSize: 11, fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 240, overflow: 'auto', cursor: 'text', userSelect: 'text' }}>
                              {file.ai_command}
                            </pre>
                          </Box>
                        )}
                      </Flex>
                    </Table.Cell>
                  </Table.Row>
                )}
              </React.Fragment>
            ))}
          </Table.Body>
        </Table.Root>
      )}

      <Flex gap="2" justify="center" mt="4" pb="4">
        <Button size="1" disabled={currentPage === 1 || loading} onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}>Previous</Button>
        <Text size="2">Page {currentPage} of {totalPages}</Text>
        <Button size="1" disabled={currentPage === totalPages || loading} onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}>Next</Button>
      </Flex>

      <CommandEditDialog
        open={!!commandModal}
        filename={commandModal?.filename}
        command={commandModal?.ai_command}
        ffprobeData={commandModal?.ffprobe_data}
        ffprobeDataNew={commandModal?.ffprobe_data_new}
        onClose={() => setCommandModal(null)}
        onSave={async (cmd) => {
          try {
            await axios.put(`/api/videos/command/${commandModal.id}`, { ai_command: cmd });
            toast('Command updated & queued for processing', 'success');
            setCommandModal(null);
            fetchFiles();
            onAction?.();
          } catch (err) {
            toast(err.response?.data?.detail || 'Failed to update command', 'error');
          }
        }}
      />

      <HistoryDialog
        open={!!historyModal}
        filename={historyModal?.filename}
        history={historyModal?.history}
        onClose={() => setHistoryModal(null)}
      />

      <ConfirmDialog
        open={!!confirm}
        message={confirm?.message}
        onCancel={() => setConfirm(null)}
        onConfirm={() => {
          if (confirm.bulk) handleBulkAction(confirm.action);
          else handleAction(confirm.id, confirm.action);
          setConfirm(null);
        }}
      />
    </>
  );
}

export default FileTable;
