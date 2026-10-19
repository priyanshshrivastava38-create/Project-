import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import AppLayout from './layouts/AppLayout';
import { firstAllowedPath } from './layouts/navConfig';
import { RequireAuth, RequirePermission } from './components/RouteGuards';
import Spinner from './components/Spinner';
import LoginPage from './pages/LoginPage';
import NoAccess from './pages/NoAccess';
import NotFound from './pages/NotFound';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AssistantPage = lazy(() => import('./pages/AssistantPage'));
const CustomersPage = lazy(() => import('./pages/CustomersPage'));
const CustomerDetailPage = lazy(() => import('./pages/CustomerDetailPage'));
const SuppliersPage = lazy(() => import('./pages/SuppliersPage'));
const OrdersPage = lazy(() => import('./pages/OrdersPage'));
const OrderFormPage = lazy(() => import('./pages/OrderFormPage'));
const OrderDetailPage = lazy(() => import('./pages/OrderDetailPage'));
const InventoryPage = lazy(() => import('./pages/InventoryPage'));
const MaterialsPage = lazy(() => import('./pages/MaterialsPage'));
const TransactionsPage = lazy(() => import('./pages/TransactionsPage'));
const ProductionBoardPage = lazy(() => import('./pages/ProductionBoardPage'));
const ProductionJobsPage = lazy(() => import('./pages/ProductionJobsPage'));
const JobDetailPage = lazy(() => import('./pages/JobDetailPage'));
const QualityPage = lazy(() => import('./pages/QualityPage'));
const DeliveriesPage = lazy(() => import('./pages/DeliveriesPage'));
const DocumentsPage = lazy(() => import('./pages/DocumentsPage'));
const DocumentDetailPage = lazy(() => import('./pages/DocumentDetailPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const UsersPage = lazy(() => import('./pages/UsersPage'));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'));

function Home() {
  const { can } = useAuth();
  return <Navigate to={firstAllowedPath(can)} replace />;
}

const guarded = (perm, el) => <RequirePermission perm={perm}>{el}</RequirePermission>;

export default function App() {
  return (
    <Suspense fallback={<div className="fullpage-center"><Spinner /></div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route index element={<Home />} />
          <Route path="dashboard" element={guarded('dashboard:read', <DashboardPage />)} />
          <Route path="assistant" element={guarded('assistant:use', <AssistantPage />)} />
          <Route path="customers" element={guarded('customers:read', <CustomersPage />)} />
          <Route path="customers/:id" element={guarded('customers:read', <CustomerDetailPage />)} />
          <Route path="suppliers" element={guarded('suppliers:read', <SuppliersPage />)} />
          <Route path="orders" element={guarded('orders:read', <OrdersPage />)} />
          <Route path="orders/new" element={guarded('orders:write', <OrderFormPage />)} />
          <Route path="orders/:id" element={guarded('orders:read', <OrderDetailPage />)} />
          <Route path="orders/:id/edit" element={guarded('orders:write', <OrderFormPage />)} />
          <Route path="inventory" element={guarded('inventory:read', <InventoryPage />)} />
          <Route path="inventory/materials" element={guarded(['inventory:read', 'products:read'], <MaterialsPage />)} />
          <Route path="inventory/transactions" element={guarded('inventory:read', <TransactionsPage />)} />
          <Route path="production" element={guarded('production:read', <ProductionBoardPage />)} />
          <Route path="production/jobs" element={guarded('production:read', <ProductionJobsPage />)} />
          <Route path="production/jobs/:id" element={guarded('production:read', <JobDetailPage />)} />
          <Route path="quality" element={guarded('quality:read', <QualityPage />)} />
          <Route path="deliveries" element={guarded('deliveries:read', <DeliveriesPage />)} />
          <Route path="documents" element={guarded('documents:read', <DocumentsPage />)} />
          <Route path="documents/:id" element={guarded('documents:read', <DocumentDetailPage />)} />
          <Route path="reports" element={guarded('reports:read', <ReportsPage />)} />
          <Route path="admin/users" element={guarded('users:manage', <UsersPage />)} />
          <Route path="admin/audit" element={guarded('audit:read', <AuditLogPage />)} />
          <Route path="no-access" element={<NoAccess />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
