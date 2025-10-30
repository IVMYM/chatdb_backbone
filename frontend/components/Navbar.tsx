import React from 'react';

export default function Navbar() {
  return (
    <header className="bg-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-8 w-8 bg-primary rounded-md" />
          <span className="font-semibold text-lg">FastNext v1</span>
        </div>
        <nav className="flex items-center space-x-4">
          <a href="/" className="text-sm">Dashboard</a>
          <a href="/system/users" className="text-sm">System</a>
          <a href="/db/inspection" className="text-sm">DB Inspect</a>
        </nav>
      </div>
    </header>
  );
}
