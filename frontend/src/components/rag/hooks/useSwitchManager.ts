import { useState, useCallback } from 'react';

export interface Switch {
  checked: boolean;
  label: string;
  tooltipText: string;
}

const useSwitchManager = () => {
  const [switches, setSwitches] = useState<Record<string, Switch>>({});

  const initializeSwitch = useCallback(
    (
      id: string,
      initialChecked: boolean,
      label: string,
      tooltipText: string
    ) => {
      setSwitches((prevSwitches) => ({
        ...prevSwitches,
        [id]: { checked: initialChecked, label, tooltipText },
      }));
    },
    []
  );

  const updateSwitch = useCallback((id: string, checked: boolean) => {
    setSwitches((prevSwitches) => ({
      ...prevSwitches,
      [id]: { ...prevSwitches[id], checked },
    }));
  }, []);

  const getSwitch = useCallback((id: string): Switch | undefined => {
    return switches[id];
  }, [switches]);

  const getAllSwitches = useCallback((): Record<string, Switch> => {
    return switches;
  }, [switches]);

  const resetSwitches = useCallback(() => {
    setSwitches({});
  }, []);

  const setSwitchesFromConfig = useCallback((config: Record<string, Switch>) => {
    setSwitches(config);
  }, []);

  return {
    switches,
    initializeSwitch,
    updateSwitch,
    getSwitch,
    getAllSwitches,
    resetSwitches,
    setSwitchesFromConfig,
  };
};

export default useSwitchManager;
