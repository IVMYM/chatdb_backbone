import React from 'react';
export default function Sidebar(){ 
  return (
    <aside className="w-64 p-4 border-r bg-white hidden md:block">
      <div className="space-y-4">
        <a href="/" className="block py-2 px-3 rounded hover:bg-gray-50">Overview</a>
        <a href="/system/users" className="block py-2 px-3 rounded hover:bg-gray-50">User Management</a>
        <a href="/db/inspection" className="block py-2 px-3 rounded hover:bg-gray-50">DB Inspection</a>
      </div>
    </aside>
  );
}
