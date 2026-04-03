import React, { useState, useEffect } from 'react';
import { Flex, Text, Box } from '@radix-ui/themes';
import axios from 'axios';
import { byteToHuman } from '../helpers';

const StatCard = ({ label, value, icon, accent }) => (
  <Box
    p="3"
    style={{
      background: accent ? 'var(--card-accent-bg)' : 'var(--card-bg)',
      borderRadius: 8,
      border: '1px solid var(--card-border)',
      minWidth: 140,
      flex: 1,
    }}
  >
    <Flex direction="column" gap="1">
      <Text size="1" color="gray">{icon} {label}</Text>
      <Text size="4" weight="bold">{value}</Text>
    </Flex>
  </Box>
);

function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    const fetch = () => axios.get('/api/videos/stats/summary').then((r) => setStats(r.data)).catch(() => {});
    fetch();
    const interval = setInterval(fetch, 15000);
    return () => clearInterval(interval);
  }, []);

  if (!stats || stats.total_videos === 0) return null;

  const savedPercent = stats.total_original_size > 0
    ? ((stats.total_saved / stats.total_original_size) * 100).toFixed(1)
    : 0;

  return (
    <Box px="4" pb="2">
      <Flex gap="3" wrap="wrap">
        <StatCard label="Total Videos" value={stats.total_videos} icon="📁" />
        <StatCard label="Total Size" value={byteToHuman(stats.total_original_size)} icon="💿" />
        <StatCard label="Space Saved" value={byteToHuman(stats.total_saved)} icon="✅" accent />
        <StatCard label="Savings" value={`${savedPercent}%`} icon="📉" accent />
        <StatCard label="Completed" value={stats.completed_count} icon="🏁" />
        <StatCard label="Processing" value={stats.processing_count} icon="⚙️" />
      </Flex>
    </Box>
  );
}

export default Dashboard;
