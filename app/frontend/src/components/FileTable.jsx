import React, { useEffect, useState, useMemo } from 'react';
import { Flex, Button, Table, Box, Tooltip, Progress, Spinner } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon, InfoCircledIcon, ResetIcon, TrashIcon } from "@radix-ui/react-icons";
import axios from 'axios';
import Filters from './Filter';

function FileTable({ status }) {
  const actionConfig = useMemo(() => ({
    pending: { positive: 'confirmed', negative: 'rejected' },
    optimized: { positive: 'accepted', negative: 'skipped' },
    ready: { revert: 'pending' },
    rejected: { delete: true },
    skipped: { delete: true },
    failed: { delete: true },
  }), []);

  const [files, setFiles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all');
  const [codecFilter, setCodecFilter] = useState('all');
  const [fileNameSearch, setFileNameSearch] = useState('');
  const [filePathSearch, setFilePathSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const itemsPerPage = 50;

  useEffect(() => {
    const fetchFilesDebounced = debounce(fetchFiles, 300);
    fetchFilesDebounced();
    return () => fetchFilesDebounced.cancel();
  }, [currentPage, sizeFilter, codecFilter, fileNameSearch, filePathSearch]);

  useEffect(() => {
    if (status === 'ready') {
      const interval = setInterval(fetchFiles, 10000);
      return () => clearInterval(interval);
    }
  }, [status]);

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    const source = axios.CancelToken.source();
    fetchFiles.cancel = () => source.cancel('Request canceled due to a new request.');

    try {
      const response = await axios.get(`/api/videos/${status}`, {
        params: {
          page: currentPage,
          limit: itemsPerPage,
          size: toByte(sizeFilter),
          codec: toCodec(codecFilter),
          name: fileNameSearch,
          directory: filePathSearch
        },
        cancelToken: source.token,
      });
      setFiles(response.data.list);
      setTotalPages(response.data.total_pages);
    } catch (err) {
      if (axios.isCancel(err)) {
        console.log('Request canceled:', err.message);
      } else {
        setError('Failed to fetch files. Please try again.');
        console.error('Error fetching files:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const toByte = (size) => {
    if (size === 'all') return null;
    const multiplier = size.endsWith('GB') ? 1e9 : size.endsWith('MB') ? 1e6 : 1;
    return parseFloat(size) * multiplier;
  };

  const toCodec = useMemo(() => (codec) => (codec === 'all' ? null : codec.toLowerCase()), []);

  const byteToGigabyte = (bytes) => {
    if (!bytes) return 'NA';
    const sizeInGB = bytes / 1e9;
    const sizeInMB = bytes / 1e6;
    return sizeInGB >= 1 ? `${sizeInGB.toFixed(2)} GB` : `${sizeInMB.toFixed(2)} MB`;
  };

  const handleAction = async (id, action) => {
    try {
      const endpoint = action === 'delete' ? `/api/videos/${id}` : `/api/videos/${id}/status`;
      const method = action === 'delete' ? 'delete' : 'post';
      const data = action !== 'delete' ? { status: action } : undefined;

      await axios({ method, url: endpoint, data });
      fetchFiles();
    } catch (err) {
      console.error(`Error performing ${action} action:`, err);
    }
  };

  const compressionPercentage = (originalSize, compressedSize) => {
    if (!originalSize || !compressedSize || originalSize <= 0) return 'NA';
    const percentage = ((originalSize - compressedSize) / originalSize) * 100;
    return `${percentage.toFixed(2)}%`;
  };

  const calculateRuntime = (ffprobe) => {
    try {
      const ffprobeData = JSON.parse(ffprobe);
      const duration = parseFloat(ffprobeData.duration);
      const formatTime = (seconds) => {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };
      return formatTime(duration);
    } catch {
      return 'NA';
    }
  };

  const calculateProgressAndETA = (ffprobe, ffmpegOut) => {
    try {
      const ffprobeData = JSON.parse(ffprobe);
      const duration = parseFloat(ffprobeData.duration);

      const timeMatch = ffmpegOut.match(/time=(\d+):(\d+):(\d+\.\d+)/);
      const speedMatch = ffmpegOut.match(/speed=([\d.]+)x/);
      const bitrateMatch = ffmpegOut.match(/bitrate=\s*([\d.]+)kbits\/s/);

      if (!timeMatch || !speedMatch) return { progressPercent: 0, estimateTimeRemaining: 'NA', expectedFileSize: 'NA', videoProcessedTime: 'NA' };

      const [_, hh, mm, ss] = timeMatch;
      const currentTimeInSeconds = (+hh) * 3600 + (+mm) * 60 + (+ss);
      const speed = parseFloat(speedMatch[1]);
      const targetBitrate = bitrateMatch ? parseFloat(bitrateMatch[1]) * 1000 : null;
      const progressPercent = ((currentTimeInSeconds / duration) * 100).toFixed(2);
      const remainingSeconds = (duration - currentTimeInSeconds) / speed;

      const formatTime = (seconds) => {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };

      const expectedFileSize = targetBitrate ? ((duration * targetBitrate) / 8) : 0;

      return {
        videoProcessedTime: formatTime(currentTimeInSeconds),
        progressPercent: Number(progressPercent),
        estimateTimeRemaining: formatTime(remainingSeconds),
        expectedFileSize: expectedFileSize ? byteToGigabyte(expectedFileSize) : 'NA',
      };
    } catch {
      return { progressPercent: 0, estimateTimeRemaining: 'NA', expectedFileSize: 'NA', videoProcessedTime: 'NA'};
    }
  };

  return (
    <>
      <Box p="4" style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#f3f4f6' }}>
        <Filters
          sizeFilter={sizeFilter}
          setSizeFilter={setSizeFilter}
          codecFilter={codecFilter}
          setCodecFilter={setCodecFilter}
          fileNameSearch={fileNameSearch}
          setFileNameSearch={setFileNameSearch}
          filePathSearch={filePathSearch}
          setFilePathSearch={setFilePathSearch}
        />
      </Box>
      {loading ? (
        <Flex justify="center" mt="4">
          <Spinner size="3" />
        </Flex>
      ) : error ? (
        <Flex justify="center" mt="4" color="red">
          {error}
        </Flex>
      ) : (
        <Table.Root size="1" variant="surface">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeaderCell minWidth="70%">Name</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Codec</Table.ColumnHeaderCell>
              <Table.ColumnHeaderCell>Runtime</Table.ColumnHeaderCell>
              {status === 'optimized' && <Table.ColumnHeaderCell>Compressed</Table.ColumnHeaderCell>}
              <Table.ColumnHeaderCell>Size</Table.ColumnHeaderCell>
              {status === 'ready' && <Table.ColumnHeaderCell>Progress</Table.ColumnHeaderCell>}
              {Object.keys(actionConfig).includes(status) && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {files.map((file, index) => (
              <Table.Row
                key={file.id}
                style={{
                  backgroundColor: index % 2 === 0 ? '#f9fafb' : 'transparent',
                }}
              >
                <Table.Cell>
                  {file.filename}{' '}
                  <Tooltip content={`Path: ${file.filepath}`}>
                    <InfoCircledIcon />
                  </Tooltip>
                </Table.Cell>
                <Table.Cell>
                  {file.original_codec}
                  {file.new_codec && ` | ${file.new_codec}`}
                </Table.Cell>
                <Table.Cell>
                  {file.ffprobe_data ? calculateRuntime(file.ffprobe_data) : 'NA'}
                </Table.Cell>
                {status === 'optimized' && <Table.Cell>{compressionPercentage(file.original_size, file.optimized_size)}</Table.Cell>}
                <Table.Cell>
                  {byteToGigabyte(Number(file.original_size))}
                  {file.optimized_size && ` | ${byteToGigabyte(Number(file.optimized_size))}`}
                </Table.Cell>
                {status === 'ready' && (
                  <Table.Cell>
                    <Progress
                      size="3"
                      value={calculateProgressAndETA(file.ffprobe_data, file.progress).progressPercent}
                      variant="classic"
                    />
                    {calculateProgressAndETA(file.ffprobe_data, file.progress).estimateTimeRemaining} | {calculateProgressAndETA(file.ffprobe_data, file.progress).expectedFileSize} | {calculateProgressAndETA(file.ffprobe_data, file.progress).videoProcessedTime}
                  </Table.Cell>
                )}
                {Object.keys(actionConfig).includes(status) && (
                  <Table.Cell>
                    <Flex gap="2">
                      {actionConfig[status]?.positive && (
                        <Button
                          size="1"
                          color="green"
                          onClick={() => handleAction(file.id, actionConfig[status].positive)}
                        >
                          <CheckIcon />
                        </Button>
                      )}
                      {actionConfig[status]?.negative && (
                        <Button
                          size="1"
                          color="yellow"
                          onClick={() => handleAction(file.id, actionConfig[status].negative)}
                        >
                          <Cross2Icon />
                        </Button>
                      )}
                      {actionConfig[status]?.revert && (
                        <Button
                          size="1"
                          color="blue"
                          onClick={() => handleAction(file.id, actionConfig[status].revert)}
                        >
                          <ResetIcon />
                        </Button>
                      )}
                      {actionConfig[status]?.delete && (
                        <Button
                          size="1"
                          color="red"
                          onClick={() => handleAction(file.id, 'delete')}
                        >
                          <TrashIcon />
                        </Button>
                      )}
                    </Flex>
                  </Table.Cell>
                )}
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      )}
      <Flex gap="2" justify="center" mt="4">
        <Button
          size="1"
          disabled={currentPage === 1 || loading}
          onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
        >
          Previous
        </Button>
        <span>
          Page {currentPage} of {totalPages}
        </span>
        <Button
          size="1"
          disabled={currentPage === totalPages || loading}
          onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
        >
          Next
        </Button>
      </Flex>
    </>
  );
}

export default FileTable;

// Helper function for debouncing
function debounce(func, wait) {
  let timeout;
  const debounced = (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
  debounced.cancel = () => clearTimeout(timeout);
  return debounced;
}
