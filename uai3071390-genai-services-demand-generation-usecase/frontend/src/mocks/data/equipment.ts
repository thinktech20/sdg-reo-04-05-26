/**
 * Mock equipment and train data for MSW
 * Migrated from sdg-risk-analyser-archive
 */

export interface Equipment {
  serialNumber: string
  equipmentType: 'Gas Turbine' | 'Generator' | 'Steam Turbine'
  equipmentCode: string
  model: string
  site: string
  commercialOpDate: string
  totalEOH: number
  totalStarts: number
  coolingType?: string
}

export interface Train {
  id: string
  trainName: string
  site: string
  trainType: string
  outageId: string
  outageType: 'Major' | 'Minor'
  startDate: string
  endDate: string
  equipment: Equipment[]
}

export const MOCK_INSTALL_BASE: Equipment[] = [
  {
    serialNumber: 'GT12345',
    equipmentType: 'Gas Turbine',
    equipmentCode: '7FA.05',
    model: '7FA',
    site: 'Moss Landing',
    commercialOpDate: '1999-08-15',
    totalEOH: 145234,
    totalStarts: 892,
    coolingType: 'Air-Cooled',
  },
  {
    serialNumber: '92307',
    equipmentType: 'Generator',
    equipmentCode: 'W88',
    model: 'W88',
    site: 'Moss Landing',
    commercialOpDate: '1999-08-15',
    totalEOH: 145234,
    totalStarts: 892,
    coolingType: 'Hydrogen-Cooled',
  },
  {
    serialNumber: 'GT67890',
    equipmentType: 'Gas Turbine',
    equipmentCode: '7FA.05',
    model: '7FA',
    site: 'Pittsburg',
    commercialOpDate: '2001-05-20',
    totalEOH: 132456,
    totalStarts: 745,
    coolingType: 'Air-Cooled',
  },
  {
    serialNumber: 'GEN54321',
    equipmentType: 'Generator',
    equipmentCode: 'W88',
    model: 'W88',
    site: 'Pittsburg',
    commercialOpDate: '2001-05-20',
    totalEOH: 132456,
    totalStarts: 745,
    coolingType: 'Hydrogen-Cooled',
  },
  {
    serialNumber: 'GT11111',
    equipmentType: 'Gas Turbine',
    equipmentCode: '9FA.03',
    model: '9FA',
    site: 'Delta Energy',
    commercialOpDate: '2005-03-10',
    totalEOH: 98234,
    totalStarts: 523,
    coolingType: 'Closed-Loop Water',
  },
  {
    serialNumber: 'GEN22222',
    equipmentType: 'Generator',
    equipmentCode: 'A13',
    model: 'A13',
    site: 'Colstrip',
    commercialOpDate: '1986-11-22',
    totalEOH: 287456,
    totalStarts: 342,
    coolingType: 'Hydrogen-Cooled',
  },
  {
    serialNumber: 'ST88888',
    equipmentType: 'Steam Turbine',
    equipmentCode: 'D11',
    model: 'D11',
    site: 'Colstrip',
    commercialOpDate: '1986-11-22',
    totalEOH: 287456,
    totalStarts: 342,
  },
  {
    serialNumber: 'ST99999',
    equipmentType: 'Steam Turbine',
    equipmentCode: 'STF-A60',
    model: 'STF-A',
    site: 'Moss Landing',
    commercialOpDate: '1999-08-15',
    totalEOH: 145234,
    totalStarts: 892,
  },
]

export const MOCK_TRAINS: Train[] = [
  {
    id: 'train-001',
    trainName: '1-1 Train',
    site: 'Moss Landing',
    trainType: 'Combined Cycle 1x1',
    outageId: 'ML-2025-001',
    outageType: 'Major',
    startDate: '2025-04-15',
    endDate: '2025-06-30',
    equipment: [
      MOCK_INSTALL_BASE[0]!, // GT12345
      MOCK_INSTALL_BASE[1]!, // 92307
      MOCK_INSTALL_BASE[7]!, // ST99999
    ],
  },
  {
    id: 'train-002',
    trainName: '2-1 Train',
    site: 'Pittsburg',
    trainType: 'Simple Cycle',
    outageId: 'PIT-2025-002',
    outageType: 'Major',
    startDate: '2025-09-01',
    endDate: '2025-11-15',
    equipment: [
      MOCK_INSTALL_BASE[2]!, // GT67890
      MOCK_INSTALL_BASE[3]!, // GEN54321
    ],
  },
  {
    id: 'train-003',
    trainName: '3-1 Train',
    site: 'Delta Energy',
    trainType: 'Simple Cycle',
    outageId: 'DE-2025-003',
    outageType: 'Minor',
    startDate: '2025-06-10',
    endDate: '2025-07-05',
    equipment: [MOCK_INSTALL_BASE[4]!], // GT11111
  },
  {
    id: 'train-004',
    trainName: 'Unit 3',
    site: 'Colstrip',
    trainType: 'Combined Cycle 2x1',
    outageId: 'COL-2026-001',
    outageType: 'Major',
    startDate: '2026-03-01',
    endDate: '2026-05-31',
    equipment: [
      MOCK_INSTALL_BASE[5]!, // GEN22222
      MOCK_INSTALL_BASE[6]!, // ST88888
    ],
  },
]
