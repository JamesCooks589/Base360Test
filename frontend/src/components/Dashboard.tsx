import React, { useEffect, useState } from "react";
import { RevenueSummary } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";

interface Property {
  id: string;
  name: string;
  timezone: string;
}

const Dashboard: React.FC = () => {
  // Properties are loaded per tenant; IDs are only unique within a tenant
  const [properties, setProperties] = useState<Property[]>([]);
  const [selectedProperty, setSelectedProperty] = useState('');
  const [propertiesError, setPropertiesError] = useState('');
  // "YYYY-MM" from the month picker; empty means all time
  const [selectedMonth, setSelectedMonth] = useState('');

  useEffect(() => {
    SecureAPI.getDashboardProperties()
      .then((list) => {
        setProperties(list);
        setSelectedProperty(list[0]?.id ?? '');
      })
      .catch((err) => {
        setPropertiesError('Failed to load properties');
        console.error(err);
      });
  }, []);

  const [year, month] = selectedMonth ? selectedMonth.split('-').map(Number) : [undefined, undefined];
  const activeProperty = properties.find((p) => p.id === selectedProperty);

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <div className="mb-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
              <div>
                <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
                <p className="text-sm lg:text-base text-gray-600">
                  Monthly performance insights for your properties
                </p>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-4">
              {/* Month Selector */}
              <div className="flex flex-col sm:items-end">
                <label className="text-xs font-medium text-gray-700 mb-1">Month</label>
                <div className="flex gap-2">
                  <input
                    type="month"
                    value={selectedMonth}
                    onChange={(e) => setSelectedMonth(e.target.value)}
                    className="block px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                  />
                  {selectedMonth && (
                    <button
                      type="button"
                      onClick={() => setSelectedMonth('')}
                      className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                      All time
                    </button>
                  )}
                </div>
              </div>

              {/* Property Selector */}
              <div className="flex flex-col sm:items-end">
                <label className="text-xs font-medium text-gray-700 mb-1">Select Property</label>
                <select
                  value={selectedProperty}
                  onChange={(e) => setSelectedProperty(e.target.value)}
                  className="block w-full sm:w-auto min-w-[200px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                >
                  {properties.map((property) => (
                    <option key={property.id} value={property.id}>
                      {property.name}
                    </option>
                  ))}
                </select>
              </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {propertiesError && (
              <div className="p-4 text-red-500 bg-red-50 rounded-lg">{propertiesError}</div>
            )}
            {selectedProperty && (
              <>
                <p className="text-sm text-gray-500">
                  {selectedMonth ? `Reservations checking in during ${selectedMonth}` : 'All reservations'}
                  {activeProperty && ` (property local time: ${activeProperty.timezone})`}
                </p>
                <RevenueSummary propertyId={selectedProperty} month={month} year={year} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
