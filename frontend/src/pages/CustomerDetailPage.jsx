import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getCustomer } from '../api/customers';
import { listOrders } from '../api/orders';
import { useAsync } from '../hooks/useAsync';
import { usePagination } from '../hooks/usePagination';
import { useAuth } from '../context/AuthContext';
import { Button, Card, DataTable, ErrorState, KeyValue, PageHeader, Spinner, StatusBadge } from '../components';
import { formatDate, formatMoney } from '../utils/format';
import { CustomerFormModal } from './CustomersPage';

export default function CustomerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { can } = useAuth();
  const customer = useAsync(() => getCustomer(id), [id]);
  const pg = usePagination({}, { pageSize: 10 });
  const orders = useAsync(() => listOrders({ customer_id: id, page: pg.page, page_size: pg.pageSize }), [id, pg.page, pg.pageSize], { enabled: can('orders:read') });
  const [editing, setEditing] = useState(false);
  const c = customer.data;

  if (customer.error) return <ErrorState error={customer.error} onRetry={customer.reload} />;
  if (!c) return <Spinner />;

  return (
    <>
      <PageHeader
        title={c.company_name}
        meta={<StatusBadge status={c.status} />}
        subtitle={c.code}
        breadcrumbs={[{ label: 'Customers', to: '/customers' }, { label: c.code }]}
        actions={(
          <>
            {can('customers:write') ? <Button icon="edit" onClick={() => setEditing(true)}>Edit</Button> : null}
            {can('orders:write') && c.status === 'ACTIVE' ? <Button variant="primary" icon="plus" onClick={() => navigate(`/orders/new?customer_id=${c.id}`)}>New order</Button> : null}
          </>
        )}
      />
      <Card title="Details">
        <KeyValue items={[
          ['Contact person', c.contact_person], ['Email', c.email], ['Phone', c.phone], ['Tax ID', c.tax_id],
          ['Total orders', c.order_count], ['Open orders', c.open_order_count],
          ['Billing address', c.billing_address], ['Shipping address', c.shipping_address],
          ['Created', formatDate(c.created_at)], ['Updated', formatDate(c.updated_at)],
        ]} />
      </Card>
      {can('orders:read') ? (
        <Card title="Orders" padded={false}>
          <DataTable
            columns={[
              { key: 'order_number', header: 'Order', render: (r) => <strong>{r.order_number}</strong> },
              { key: 'order_date', header: 'Order date', render: (r) => formatDate(r.order_date) },
              { key: 'required_date', header: 'Required', render: (r) => formatDate(r.required_date) },
              { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              { key: 'total', header: 'Total', align: 'right', render: (r) => formatMoney(r.total, r.currency) },
            ]}
            rows={orders.data?.items}
            loading={orders.loading}
            error={orders.error}
            onRetry={orders.reload}
            page={pg.page}
            pageSize={pg.pageSize}
            total={orders.data?.total}
            onPageChange={pg.setPage}
            onRowClick={(r) => navigate(`/orders/${r.id}`)}
            emptyTitle="No orders for this customer yet"
          />
        </Card>
      ) : null}
      <CustomerFormModal open={editing} customer={c} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); customer.reload(); }} />
    </>
  );
}
