import React from 'react';
import { Box, Flex, Select, Text, TextField } from '@radix-ui/themes';
import { MagnifyingGlassIcon } from '@radix-ui/react-icons';

const Filters = ({
  sizeFilter,
  setSizeFilter,
  codecFilter,
  setCodecFilter,
  fileNameSearch,
  setFileNameSearch,
  filePathSearch,
  setFilePathSearch,
}) => {
  return (
    <Flex gap="4" align="center" wrap="wrap">
      <Box>
        <Text weight="bold">Filters:</Text>
      </Box>

      <Box>
        <Select.Root
          id="size-filter"
          defaultValue={sizeFilter}
          onValueChange={setSizeFilter}
        >
          <Select.Trigger aria-label="Filter by file size" />
          <Select.Content>
            <Select.Item value="all">All Sizes</Select.Item>
            <Select.Item value="200MB">{'> 200MB'}</Select.Item>
            <Select.Item value="500MB">{'> 500MB'}</Select.Item>
            <Select.Item value="800MB">{'> 800MB'}</Select.Item>
            <Select.Item value="1GB">{'> 1GB'}</Select.Item>
            <Select.Item value="1.5GB">{'> 1.5GB'}</Select.Item>
            <Select.Item value="2GB">{'> 2GB'}</Select.Item>
            <Select.Item value="2.5GB">{'> 2.5GB'}</Select.Item>
            <Select.Item value="3GB">{'> 3GB'}</Select.Item>
          </Select.Content>
        </Select.Root>
      </Box>

      <Box>
        <Select.Root
          id="codec-filter"
          defaultValue={codecFilter}
          onValueChange={setCodecFilter}
        >
          <Select.Trigger aria-label="Filter by codec" />
          <Select.Content>
            <Select.Item value="all">All Codec</Select.Item>
            <Select.Item value="HEVC">HEVC</Select.Item>
            <Select.Item value="H264">h264</Select.Item>
          </Select.Content>
        </Select.Root>
      </Box>

      <Box>
        <TextField.Root
          id="file-name-search"
          placeholder="Search by file name"
          value={fileNameSearch}
          onChange={(e) => setFileNameSearch(e.target.value)}
        >
          <TextField.Slot>
            <MagnifyingGlassIcon />
          </TextField.Slot>
        </TextField.Root>
      </Box>

      <Box>
        <TextField.Root
          id="file-path-search"
          placeholder="Search by file path"
          value={filePathSearch}
          onChange={(e) => setFilePathSearch(e.target.value)}
        >
          <TextField.Slot>
            <MagnifyingGlassIcon />
          </TextField.Slot>
        </TextField.Root>
      </Box>
    </Flex>
  );
};

export default Filters;