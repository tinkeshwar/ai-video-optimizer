import axios from 'axios';
import React, { useState, useEffect, useCallback } from 'react';
import { Flex, Text, Box, Heading, Tabs, Badge } from '@radix-ui/themes';
import FileTable from './FileTable';
import Dashboard from './Dashboard';

const TAB_CONFIG = [
  { value: 'pending', label: 'Pending', color: 'yellow' },
  { value: 'confirmed', label: 'Confirmed', color: 'blue' },
  { value: 'ready', label: 'Processing', color: 'indigo' },
  { value: 'optimized', label: 'Optimized', color: 'green' },
  { value: 'replaced', label: 'Completed', color: 'grass' },
  { value: 'rejected', label: 'Rejected', color: 'orange' },
  { value: 'skipped', label: 'Skipped', color: 'gray' },
  { value: 'failed', label: 'Failed', color: 'red' },
];

function FileList() {
  const [counts, setCounts] = useState({});
  const [activeTab, setActiveTab] = useState('pending');

  const fetchCounts = useCallback(async () => {
    try {
      const response = await axios.get('/api/videos/status/count');
      setCounts(response.data);
    } catch (err) {
      console.error('Error fetching counts:', err);
    }
  }, []);

  useEffect(() => {
    fetchCounts();
    const interval = setInterval(fetchCounts, 10000);
    return () => clearInterval(interval);
  }, [fetchCounts]);

  return (
    <Flex direction="column" gap="3">
      <Flex
        justify="between"
        align="center"
        p="3"
        style={{
          borderBottom: '1px solid var(--header-border)',
          backgroundColor: 'var(--header-bg)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <Flex align="center" gap="2">
          <Text size="5" weight="bold">💾 Disk Saver</Text>
        </Flex>
      </Flex>

      <Dashboard />

      <Box px="4" pb="4">
        <Heading style={{ padding: '.2em' }}>Files</Heading>
        <Tabs.Root value={activeTab} onValueChange={setActiveTab}>
          <Tabs.List style={{ position: 'sticky', top: 52, zIndex: 99, background: 'var(--surface-bg)' }}>
            {TAB_CONFIG.map(({ value, label, color }) => (
              <Tabs.Trigger key={value} value={value} disabled={!counts[value]}>
                <Flex align="center" gap="1">
                  {label}
                  {counts[value] > 0 && (
                    <Badge size="1" color={color} variant="soft">{counts[value]}</Badge>
                  )}
                </Flex>
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Box pt="3">
            {TAB_CONFIG.map(({ value }) => (
              <Tabs.Content key={value} value={value}>
                {activeTab === value && (
                  <FileTable status={value} onAction={fetchCounts} />
                )}
              </Tabs.Content>
            ))}
          </Box>
        </Tabs.Root>
      </Box>
    </Flex>
  );
}

export default FileList;
