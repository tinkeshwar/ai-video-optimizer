import axios from 'axios';
import React, { useState, useEffect } from 'react';
import { Flex, Text, Box, Heading, Tabs } from '@radix-ui/themes';
import FileTable from './FileTable';

function FileList() {
  const [counts, setCounts] = useState([]);

  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await axios.get(`/api/videos/status/count`);
      setCounts(response.data);
    } catch (err) {
      console.error('Error fetching files:', err);
    }
  };

  return (
    <Flex direction="column" gap="3">
      <Flex justify="between" align="center" p="3" style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#e1e1e1' }}>
        <Flex align="center" gap="2">
          <Text size="5" weight="bold">💾 Disk Saver</Text>
        </Flex>
      </Flex>

      <Box p="4">
        <Heading style={{ padding: ".2em"}}>Files</Heading>
        <Tabs.Root defaultValue="pending">
          <Tabs.List>
            <Tabs.Trigger disabled={!counts?.pending} value="pending">Pending ({ counts?.pending || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.ready} value="ready">Ready ({ counts?.ready || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.optimized} value="optimized">Optimized ({ counts?.optimized || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.replaced} value="replaced">Completed ({ counts?.replaced || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.rejected} value="rejected">Rejected ({ counts?.rejected || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.skipped} value="skipped">Skipped ({ counts?.skipped || 0})</Tabs.Trigger>
            <Tabs.Trigger disabled={!counts?.failed} value="failed">Failed ({ counts?.failed || 0})</Tabs.Trigger>
          </Tabs.List>
          <Box pt="3">
            <Tabs.Content value="pending"><FileTable status='pending' /></Tabs.Content>
            <Tabs.Content value="ready"><FileTable status='ready' /></Tabs.Content>
            <Tabs.Content value="optimized"><FileTable status='optimized' /></Tabs.Content>
            <Tabs.Content value="replaced"><FileTable status='replaced' /></Tabs.Content>
            <Tabs.Content value="rejected"><FileTable status='rejected' /></Tabs.Content>
            <Tabs.Content value="skipped"><FileTable status='skipped' /></Tabs.Content>
            <Tabs.Content value="failed"><FileTable status='failed' /></Tabs.Content>
          </Box>
        </Tabs.Root>
      </Box>
    </Flex>  
  )
}

export default FileList;
