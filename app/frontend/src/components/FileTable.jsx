import React from 'react';
import { Flex, Button, Table, Box } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon, ResetIcon, TrashIcon } from "@radix-ui/react-icons";
import { useEffect, useState } from 'react';
import axios from 'axios';
import Filters from './Filter';

function FileTable({ status }) {
  const actionOn = ['pending', 'optimized'];
  const revertOn = ['ready'];
  const deleteOn = ['rejected', 'skipped', 'failed'];

  const [files, setFiles] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [sizeFilter, setSizeFilter] = useState('all');
  const [codecFilter, setCodecFilter] = useState('all');
  const itemsPerPage = 50;

  useEffect(() => {
    fetchFiles();
  }, [currentPage, sizeFilter, codecFilter]);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`/api/videos/${status}`, {
        params: {
          page: currentPage,
          limit: itemsPerPage,
          size: toByte(sizeFilter),
          codec: toCodec(codecFilter)
        },
      });
      setFiles(response.data.list);
      setTotalPages(response.data.total_pages);
    } catch (err) {
      console.error('Error fetching files:', err);
    }
  };

  const toByte = (size) => {
    if (!size || size === 'all') return null;
    if (size.endsWith('GB')) return parseFloat(size) * (1000 * 1000 * 1000);
    if (size.endsWith('MB')) return parseFloat(size) * (1000 * 1000);
  };

  const toCodec = (codec) => {
    if (!codec || codec === 'all') return null;
    if (codec === 'HEVC') return 'hevc';
    if (codec === 'H264') return 'h264';
  };

  const byteToGigabyte = (bytes) => {
    if (!bytes) return 'NA';
    const sizeInGB = bytes / (1000 * 1000 * 1000);
    const sizeInMB = bytes / (1000 * 1000);
    return sizeInGB >= 1 ? `${sizeInGB.toFixed(2)} GB` : `${sizeInMB.toFixed(2)} MB`;
  };

  const actionPositive = async (id) => {
    let newStatus = (status === 'pending') ? 'confirmed' : (status === 'optimized' ? 'accepted' : 'failed');
    try {
      const response = await axios.post(`/api/videos/${id}/status`, { status: newStatus });
      console.log('File accepted:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error accepting file:', err);
    }
  };

  const actionNegative = async (id) => {
    let newStatus = (status === 'pending') ? 'rejected' : (status === 'optimized' ? 'skipped' : 'failed');
    try {
      const response = await axios.post(`/api/videos/${id}/status`, { status: newStatus });
      console.log('File rejected:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error rejecting file:', err);
    }
  };

  const actionRevert = async (id) => {
    try {
      const response = await axios.post(`/api/videos/${id}/status`, { status: 'pending' });
      console.log('File reverted:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error reverting file:', err);
    }
  };

  const actionDelete = async (id) => {
    try {
      const response = await axios.delete(`/api/videos/${id}`);
      console.log('File deleted:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error deleting file:', err);
    }
  };

  return (
    <>
      <Box p="4" style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#f3f4f6' }}>
        <Filters sizeFilter={sizeFilter} setSizeFilter={setSizeFilter} codecFilter={codecFilter} setCodecFilter={setCodecFilter} />
      </Box>
      <Table.Root size="1">
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Path</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Codec</Table.ColumnHeaderCell>
            <Table.ColumnHeaderCell>Size</Table.ColumnHeaderCell>
            {[...actionOn, ...revertOn, ...deleteOn].includes(status) && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {files.map((file) => (
            <Table.Row key={file.id}>
              <Table.Cell>{file.filename}</Table.Cell>
              <Table.Cell>{file.filepath}</Table.Cell>
              <Table.Cell>
                {file.original_codec}
                {file.new_codec && ` | ${file.new_codec}`}
              </Table.Cell>
              <Table.Cell>
                {byteToGigabyte(Number(file.original_size))}
                {file.optimized_size && `|${byteToGigabyte(Number(file.optimized_size))}`}
              </Table.Cell>
              {[...actionOn, ...revertOn, ...deleteOn].includes(status) && <Table.Cell>
                <Flex gap="2">
                  {actionOn.includes(status) && <Button size="1" color="green" onClick={() => actionPositive(file.id)}><CheckIcon /></Button>}
                  {actionOn.includes(status) && <Button size="1" color="yellow" onClick={() => actionNegative(file.id)}><Cross2Icon /></Button>}
                  {revertOn.includes(status) && <Button size="1" color="blue" onClick={() => actionRevert(file.id)}><ResetIcon /></Button>}
                  {deleteOn.includes(status) && <Button size="1" color="red" onClick={() => actionDelete(file.id)}><TrashIcon /></Button>}
                </Flex>
              </Table.Cell>}
            </Table.Row>
          ))}
        </Table.Body>
      </Table.Root>
      <Flex gap="2" justify="center" mt="4">
        <Button
          size="1"
          disabled={currentPage === 1}
          onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
        >
          Previous
        </Button>
        <span>Page {currentPage} of {totalPages}</span>
        <Button
          size="1"
          disabled={currentPage === totalPages}
          onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
        >
          Next
        </Button>
      </Flex>
    </>
  );
}

export default FileTable;
