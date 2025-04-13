import React from 'react';
import { Flex, Button, Table } from '@radix-ui/themes';
import { CheckIcon, Cross2Icon } from "@radix-ui/react-icons";
import { useEffect, useState } from 'react';
import axios from 'axios';

const API_HOST = 'http://localhost:8000';

function FileTable({ status}) {
  const actionOn = ['pending', 'optimized'];
  const [files, setFiles] = useState([]);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`${API_HOST}/api/videos/${status}`);
      setFiles(response.data);
    } catch (err) {
      console.error('Error fetching files:', err);
    }
  };

  const byteToGigabyte = (bytes) => {
    if(!bytes) return 'NA';
    const sizeInGB = bytes / (1000 * 1000 * 1000);
    const sizeInMB = bytes / (1000 * 1000);
    return sizeInGB >= 1 ? `${sizeInGB.toFixed(2)} GB` : `${sizeInMB.toFixed(2)} MB`;
  } 
 
  const actionPositive = async (id) => {
    let newStatus = (status === 'pending') ? 'confirmed' : (status === 'optimized' ? 'accepted' : 'failed');
    try {
      const response = await axios.post(`${API_HOST}/api/videos/${id}/status`, { status: newStatus });
      console.log('File accepted:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error accepting file:', err);
    }
  }
  const actionNegative = async (id) => {
    let newStatus = (status === 'pending') ? 'rejected' : (status === 'optimized' ? 'skipped' : 'failed');
    try {
      const response = await axios.post(`${API_HOST}/api/videos/${id}/status`, { status: newStatus });
      console.log('File rejected:', response.data);
      fetchFiles();
    } catch (err) {
      console.error('Error rejecting file:', err);
    }
  }

  return (
    <Table.Root size="1">
      <Table.Header>
        <Table.Row>
          <Table.ColumnHeaderCell>Name</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Path</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Size</Table.ColumnHeaderCell>
          <Table.ColumnHeaderCell>Optimized</Table.ColumnHeaderCell>
          {actionOn.includes(status) && <Table.ColumnHeaderCell>Action</Table.ColumnHeaderCell>}
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {files.map((file) => (
          <Table.Row key={file.id}>
            <Table.Cell>{file.filename}</Table.Cell>
            <Table.Cell>{file.filepath}</Table.Cell>
            <Table.Cell>{byteToGigabyte(Number(file.original_size))}</Table.Cell>
            <Table.Cell>{byteToGigabyte(Number(file.optimized_size))}</Table.Cell>
            {actionOn.includes(status) && <Table.Cell>
              <Flex gap="2">
                <Button size="1" color="green" onClick={() => actionPositive(file.id)}><CheckIcon/></Button>
                <Button size="1" color="red" onClick={() => actionNegative(file.id)}><Cross2Icon/></Button>
              </Flex>
            </Table.Cell>}
          </Table.Row>
        ))}
      </Table.Body>
    </Table.Root>
  )
}

export default FileTable;