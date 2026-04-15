import { useMutation, useQuery } from '@tanstack/react-query'
import { billingApi } from '../api/billing'
import { getErrorMessage } from '../api/client'
import { Layout } from '../components/Layout'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

export function BillingPage() {
  const {
    data: sub,
    isLoading,
    isError,
    error: subError,
  } = useQuery({
    queryKey: ['subscription'],
    queryFn: () => billingApi.getSubscription().then((r) => r.data),
  })

  const checkoutMutation = useMutation({
    mutationFn: () => billingApi.createCheckout().then((r) => r.data),
    onSuccess: ({ checkout_url }) => {
      window.location.href = checkout_url
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => billingApi.createPortal().then((r) => r.data),
    onSuccess: ({ portal_url }) => {
      window.location.href = portal_url
    },
  })

  const actionError =
    (checkoutMutation.isError && getErrorMessage(checkoutMutation.error)) ||
    (portalMutation.isError && getErrorMessage(portalMutation.error))

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Billing</h1>
        <p className="text-sm text-gray-500 mt-0.5">Manage your subscription</p>
      </div>

      {isLoading && (
        <p className="text-sm text-gray-400 text-center py-12">Loading…</p>
      )}

      {/* Billing not enabled on backend */}
      {isError && (
        <Card className="p-6 text-center">
          <p className="text-sm text-gray-500">
            {getErrorMessage(subError).includes('not enabled')
              ? 'Billing is not enabled on this server.'
              : getErrorMessage(subError)}
          </p>
        </Card>
      )}

      {sub && (
        <div className="max-w-md space-y-4">
          {/* Current plan card */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">
                  Current plan
                </p>
                <p className="text-2xl font-bold text-gray-900 mt-1 capitalize">
                  {sub.plan}
                </p>
              </div>
              {sub.plan === 'pro' && (
                <span className="bg-indigo-100 text-indigo-700 text-xs font-semibold px-2 py-1 rounded-full">
                  Pro
                </span>
              )}
            </div>

            {sub.status && (
              <p className="text-sm text-gray-500 mb-1">
                Status:{' '}
                <span className="font-medium text-gray-700 capitalize">{sub.status}</span>
              </p>
            )}

            {sub.current_period_end && (
              <p className="text-sm text-gray-500 mb-1">
                {sub.cancel_at_period_end ? 'Cancels' : 'Renews'} on{' '}
                <span className="font-medium text-gray-700">
                  {fmt(sub.current_period_end)}
                </span>
              </p>
            )}

            {sub.cancel_at_period_end && (
              <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mt-3">
                Your subscription will cancel at the end of the billing period.
              </p>
            )}
          </Card>

          {/* Action card */}
          <Card className="p-6">
            {actionError && (
              <p className="text-sm text-red-600 mb-4">{actionError}</p>
            )}

            {sub.plan === 'free' ? (
              <div>
                <h3 className="font-semibold text-gray-900 mb-1">Upgrade to Pro</h3>
                <p className="text-sm text-gray-500 mb-4">
                  Unlimited analyses, full history, priority support.
                </p>
                <Button
                  className="w-full"
                  loading={checkoutMutation.isPending}
                  onClick={() => checkoutMutation.mutate()}
                >
                  Upgrade to Pro →
                </Button>
              </div>
            ) : (
              <div>
                <h3 className="font-semibold text-gray-900 mb-1">Manage subscription</h3>
                <p className="text-sm text-gray-500 mb-4">
                  Update payment method, view invoices, or cancel.
                </p>
                <Button
                  variant="secondary"
                  className="w-full"
                  loading={portalMutation.isPending}
                  onClick={() => portalMutation.mutate()}
                >
                  Open billing portal →
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}
    </Layout>
  )
}
