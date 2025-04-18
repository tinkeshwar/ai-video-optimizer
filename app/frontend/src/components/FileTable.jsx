import React, { useEffect, useState } from 'react';
import { Flex, Button, Table, Box, Tooltip } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon, InfoCircledIcon, ResetIcon, TrashIcon } from "@radix-ui/react-icons";
import axios from 'axios';
import Filters from './Filter';

function FileTable({ status }) {
  const actionConfig = {
    pending: { positive: 'confirmed', negative: 'rejected' },
    optimized: { positive: 'accepted', negative: 'skipped' },
    ready: { revert: 'pending' },
    rejected: { delete: true },
    skipped: { delete: true },
    failed: { delete: true },
  };

  const [files, setFiles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all');
  const [codecFilter, setCodecFilter] = useState('all');
  const itemsPerPage = 50;

  useEffect(() => {
    fetchFiles();
  }, [currentPage, sizeFilter, codecFilter]);

  useEffect(() => {
    if (status === 'ready') {
      const interval = setInterval(fetchFiles, 10000);
      return () => clearInterval(interval);
    }
  }, [status, currentPage, sizeFilter, codecFilter]);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`/api/videos/${status}`, {
        params: {
          page: currentPage,
          limit: itemsPerPage,
          size: toByte(sizeFilter),
          codec: toCodec(codecFilter),
        },
      });
      setFiles(response.data.list);
      setTotalPages(response.data.total_pages);
    } catch (err) {
      console.error('Error fetching files:', err);
    }
  };

  const toByte = (size) => {
    if (size === 'all') return null;
    const multiplier = size.endsWith('GB') ? 1e9 : size.endsWith('MB') ? 1e6 : 1;
    return parseFloat(size) * multiplier;
  };

  const toCodec = (codec) => (codec === 'all' ? null : codec.toLowerCase());

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

      const response = await axios({ method, url: endpoint, data });
      console.log(`File ${action}:`, response.data);
      fetchFiles();
    } catch (err) {
      console.error(`Error performing ${action} action:`, err);
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
        />
      </Box>
      <Table.Root size="1">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Codec</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Size</Table.ColumnHeaderCell>
            {status === 'ready' && <Table.ColumnHeaderCell>Progress</Table.ColumnHeaderCell>}
            {Object.keys(actionConfig).includes(status) && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {files.map((file) => (
            <Table.Row key={file.id}>
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
                {byteToGigabyte(Number(file.original_size))}
                {file.optimized_size && ` | ${byteToGigabyte(Number(file.optimized_size))}`}
              </Table.Cell>
              {status === 'ready' && <Table.Cell>{file.progress || 'NA'}</Table.Cell>}
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
      <Flex gap="2" justify="center" mt="4">
        <Button
          size="1"
          disabled={currentPage === 1}
          onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
        >
          Previous
        </Button>
        <span>
          Page {currentPage} of {totalPages}
        </span>
        <Button
          size="1"
          disabled={currentPage === totalPages}
          onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
        >
          Next
        </Button>
      </Flex>
    </>
  );
}

export default FileTable;
