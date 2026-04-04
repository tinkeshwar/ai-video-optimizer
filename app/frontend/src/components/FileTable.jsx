import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Flex, Button, Table, Box, Tooltip, Progress, Spinner, Text, Checkbox } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon, InfoCircledIcon, ResetIcon, TrashIcon, ChevronUpIcon, ChevronDownIcon, CodeIcon, CountdownTimerIcon, Pencil2Icon, CheckCircledIcon } from '@radix-ui/react-icons';
import axios from 'axios';
import Filters from './Filter';
import ConfirmDialog from './ConfirmDialog';
import HistoryDialog from './HistoryDialog';
import CommandEditDialog from './CommandEditDialog';
import StreamSelectDialog from './StreamSelectDialog';
import { useToast } from './Toast';
import { byteToHuman, runtimeFromProbe, compressionPercent, progressFromProbe, relativeTime, formatStreamLabel } from '../helpers';

const ACTION_CONFIG = {
  pending: { positive: 'confirmed', negative: 'rejected', complete: 'replaced', delete: true },
  confirmed: { revert: 'pending' },
  optimized: { positive: 'accepted', negative: 'skipped' },
  ready: { revert: 'pending' },
  rejected: { delete: true },
  skipped: { delete: true },
  failed: { delete: true },
};

const DESTRUCTIVE = new Set(['rejected', 'skipped', 'delete', 'replaced']);

function FileTable({ status, onAction }) {
  const toast = useToast();
  const [files, setFiles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all');
  const [codecFilter, setCodecFilter] = useState('all');
  const [fileNameSearch, setFileNameSearch] = useState('');
  const [filePathSearch, setFilePathSearch] = useState('');
  const [streamTierFilter, setStreamTierFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [sortBy, setSortBy] = useState(null);
  const [sortOrder, setSortOrder] = useState('asc');
  const [expandedId, setExpandedId] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [historyModal, setHistoryModal] = useState(null);
  const [commandModal, setCommandModal] = useState(null);
  const [streamModal, setStreamModal] = useState(null);
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

  const initialLoadDone = React.useRef(false);

  const fetchFiles = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError(null);
    }
    try {
      const response = await axios.get(`/api/videos/${status}`, {
        params: {
          page: currentPage, limit: itemsPerPage,
          size: toByte(sizeFilter), codec: toCodec(codecFilter),
          name: fileNameSearch, directory: filePathSearch,
          sort_by: sortBy, sort_order: sortOrder,
          ...(status === 'pending' && streamTierFilter !== 'all' ? { stream_tier: streamTierFilter } : {}),
        },
      });
      setFiles(response.data.list);
      setTotalPages(response.data.total_pages);
      if (!background) setSelected(new Set());
      initialLoadDone.current = true;
    } catch (err) {
      if (!axios.isCancel(err) && !background) setError('Failed to fetch files.');
    } finally {
      if (!background) setLoading(false);
    }
  }, [currentPage, sizeFilter, codecFilter, fileNameSearch, filePathSearch, sortBy, sortOrder, status, toCodec, streamTierFilter]);

  useEffect(() => {
    initialLoadDone.current = false;
    const timer = setTimeout(() => fetchFiles(false), 300);
    return () => clearTimeout(timer);
  }, [fetchFiles]);

  const hasOpenDialog = !!(confirm || streamModal || commandModal || historyModal);

  useEffect(() => {
    if (hasOpenDialog) return;
    if (['ready', 'processing', 'pending', 'confirmed', 'optimized'].includes(status)) {
      const interval = setInterval(() => fetchFiles(true), 10000);
      return () => clearInterval(interval);
    }
  }, [status, fetchFiles, hasOpenDialog]);

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
    if (action === 'confirmed' && status === 'pending') {
      const file = files.find(f => f.id === id);
      const audio = safeParseJson(file?.audio_streams);
      const subs = safeParseJson(file?.subtitle_streams);
      // Multi-audio or has subtitles — open stream selection dialog
      if (audio.length > 1 || subs.length > 0) {
        setStreamModal(file);
        return;
      }
      // Single audio, no subs — auto-select and confirm
      if (audio.length === 1) {
        handleStreamConfirm(id, audio[0], null);
        return;
      }
    }
    if (DESTRUCTIVE.has(action)) {
      setConfirm({ id, action, message: `Are you sure you want to ${action === 'delete' ? 'delete' : action} this video?` });
    } else {
      handleAction(id, action);
    }
  };

  const safeParseJson = (str) => {
    try { return JSON.parse(str) || []; } catch { return []; }
  };

  const safeParseObj = (str) => {
    try { return typeof str === 'string' ? JSON.parse(str) : str; } catch { return null; }
  };

  const formatAudioDisplay = (file) => {
    if (status === 'pending') {
      const streams = safeParseJson(file.audio_streams);
      if (!streams.length) return 'NA';
      return streams.map(s => formatStreamLabel(s)).join(', ');
    }
    const sel = safeParseObj(file.selected_audio);
    return sel ? formatStreamLabel(sel) : 'NA';
  };

  const formatSubtitleDisplay = (file) => {
    if (status === 'pending') {
      const streams = safeParseJson(file.subtitle_streams);
      if (!streams.length) return 'None';
      return streams.map(s => formatStreamLabel(s)).join(', ');
    }
    const sel = safeParseObj(file.selected_subtitle);
    return sel ? formatStreamLabel(sel) : 'None';
  };

  const getStreamTier = (file) => {
    if (status !== 'pending') return null;
    const audio = safeParseJson(file.audio_streams);
    const subs = safeParseJson(file.subtitle_streams);
    if (audio.length > 1 && subs.length >= 2) return 'red';
    if (audio.length > 1) return 'yellow';
    if (audio.length === 1 && subs.length >= 2) return 'green';
    return 'white';
  };

  const TIER_ROW_BG = {
    red: 'rgba(255, 0, 0, 0.08)',
    yellow: 'rgba(255, 180, 0, 0.08)',
    green: 'rgba(0, 180, 0, 0.08)',
  };

  const TIER_TOOLTIP = {
    red: 'Multiple audio & subtitles — manual selection required, no auto-approve',
    yellow: 'Multiple audio — manual selection required, no auto-approve',
    green: 'Single audio, multiple subtitles — auto-approve eligible, subtitle selection available',
    white: 'Single audio, no/single subtitle — auto-approve eligible',
  };

  const TIER_EMOJI = { red: '🔴', yellow: '🟡', green: '🟢', white: '⚪' };
  const TIER_TEXT_COLOR = { red: 'red', yellow: 'orange', green: 'green' };

  const handleStreamConfirm = async (id, audioObj, subObj) => {
    try {
      await axios.put(`/api/videos/${id}/streams`, {
        selected_audio: audioObj,
        selected_subtitle: subObj || null,
      });
      toast('Stream selection saved & confirmed', 'success');
      setStreamModal(null);
      fetchFiles();
      onAction?.();
    } catch (err) {
      toast(err.response?.data?.detail || 'Failed to save stream selection', 'error');
    }
  };

  const confirmBulk = (action) => {
    if (action === 'confirmed' && status === 'pending') {
      // Bulk confirm: only single-audio, no-subtitle videos
      const ids = [...selected];
      const eligible = files.filter(f => {
        if (!ids.includes(f.id)) return false;
        const audio = safeParseJson(f.audio_streams);
        return audio.length === 1;
      });
      const skipped = ids.length - eligible.length;
      if (eligible.length > 0) {
        Promise.all(eligible.map(f => {
          const audio = safeParseJson(f.audio_streams);
          return axios.put(`/api/videos/${f.id}/streams`, {
            selected_audio: audio[0], selected_subtitle: null,
          });
        })).then(() => {
          toast(`Confirmed ${eligible.length} video(s)${skipped ? `, skipped ${skipped} (multi-audio, require manual selection)` : ''}`, 'success');
          fetchFiles();
          onAction?.();
        }).catch(() => toast('Bulk confirm failed', 'error'));
      } else {
        toast(`All ${skipped} selected video(s) require manual stream selection`, 'info');
      }
      return;
    }
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

  const streamModalAudio = useMemo(() => safeParseJson(streamModal?.audio_streams), [streamModal]);
  const streamModalSubs = useMemo(() => safeParseJson(streamModal?.subtitle_streams), [streamModal]);

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
            {...(status === 'pending' ? { streamTierFilter, setStreamTierFilter } : {})}
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
          {...(status === 'pending' ? { streamTierFilter, setStreamTierFilter } : {})}
        />
        {hasActions && selected.size > 0 && (
          <Flex gap="2" mt="2" align="center">
            <Text size="1" color="gray">{selected.size} selected</Text>
            {config?.positive && <Button size="1" color="green" onClick={() => confirmBulk(config.positive)}><CheckIcon /> {config.positive}</Button>}
            {config?.negative && <Button size="1" color="yellow" onClick={() => confirmBulk(config.negative)}><Cross2Icon /> {config.negative}</Button>}
            {config?.revert && <Button size="1" color="blue" onClick={() => confirmBulk(config.revert)}><ResetIcon /> Revert</Button>}
            {config?.complete && <Button size="1" color="grass" onClick={() => confirmBulk(config.complete)}><CheckCircledIcon /> Complete</Button>}
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
              {status !== 'pending' && <Table.ColumnHeaderCell>Audio</Table.ColumnHeaderCell>}
              {status !== 'pending' && <Table.ColumnHeaderCell>Subtitle</Table.ColumnHeaderCell>}
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
                <Table.Row style={{ backgroundColor: TIER_ROW_BG[getStreamTier(file)] || (index % 2 === 0 ? 'var(--row-alt-bg)' : 'transparent') }}>
                  {hasActions && (
                    <Table.Cell>
                      <Checkbox checked={selected.has(file.id)} onCheckedChange={() => toggleSelect(file.id)} />
                    </Table.Cell>
                  )}
                  <Table.Cell>
                    <Flex align="center" gap="1">
                      <Text color={TIER_TEXT_COLOR[getStreamTier(file)] || undefined}>{file.filename}</Text>
                      {getStreamTier(file) && <Tooltip content={TIER_TOOLTIP[getStreamTier(file)]}><Text size="1">{TIER_EMOJI[getStreamTier(file)]}</Text></Tooltip>}
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
                  {status !== 'pending' && <Table.Cell><Text size="1">{formatAudioDisplay(file)}</Text></Table.Cell>}
                  {status !== 'pending' && <Table.Cell><Text size="1">{formatSubtitleDisplay(file)}</Text></Table.Cell>}
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
                        {config?.complete && (
                          <Tooltip content="Mark complete">
                            <Button size="1" color="grass" onClick={() => confirmAction(file.id, config.complete)}><CheckCircledIcon /></Button>
                          </Tooltip>
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
        selectedAudio={commandModal?.selected_audio}
        selectedSubtitle={commandModal?.selected_subtitle}
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

      <StreamSelectDialog
        open={!!streamModal}
        filename={streamModal?.filename}
        audioStreams={streamModalAudio}
        subtitleStreams={streamModalSubs}
        onClose={() => setStreamModal(null)}
        onConfirm={(audioObj, subObj) => handleStreamConfirm(streamModal.id, audioObj, subObj)}
      />
    </>
  );
}

export default FileTable;
