import React from 'react';
import { Box, Flex, Select, Text } from '@radix-ui/themes';

const Filters = ({
  sizeFilter,
  setSizeFilter,
  codecFilter,
  setCodecFilter
}) => {
  return (
    <Flex gap="3">
      <Box>
        <Text>Apply Filters:</Text>
      </Box>

      <Box>
        <Select.Root defaultValue={sizeFilter} onValueChange={setSizeFilter}>
          <Select.Trigger />
          <Select.Content>
            <Select.Item value="all">All Sizes</Select.Item>
            <Select.Item value="200MB">{'> 200MB'}</Select.Item>
            <Select.Item value="500MB">{'> 500MB'}</Select.Item>
            <Select.Item value="800MB">{'> 800MB'}</Select.Item>
            <Select.Item value="1GB">{'> 1GB'}</Select.Item>
            <Select.Item value="1.5GB">{'> 1.5GB'}</Select.Item>
            <Select.Item value="2.5GB">{'> 2.5GB'}</Select.Item>
            <Select.Item value="3GB">{'> 3GB'}</Select.Item>
          </Select.Content>
        </Select.Root>
      </Box>

      <Box>
        <Select.Root defaultValue={codecFilter} onValueChange={setCodecFilter}>
          <Select.Trigger />
          <Select.Content>
            <Select.Item value="all">All Codec</Select.Item>
            <Select.Item value="HEVC">{'HEVC'}</Select.Item>
            <Select.Item value="H264">{'h264'}</Select.Item>
          </Select.Content>
        </Select.Root>
      </Box>
    </Flex>
  );
};

export default Filters;