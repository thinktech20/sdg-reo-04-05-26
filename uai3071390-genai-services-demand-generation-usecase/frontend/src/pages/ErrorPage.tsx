import { useRouteError, isRouteErrorResponse, Link } from 'react-router-dom'
import { Box, Typography, Button, Container, Paper } from '@mui/material'
import { Error as ErrorIcon, Home } from '@mui/icons-material'

/**
 * Error page component
 * Displays user-friendly error messages for routing errors
 */
const ErrorPage = () => {
  const error = useRouteError()

  let errorMessage = 'An unexpected error occurred'
  let errorStatus = '500'

  if (isRouteErrorResponse(error)) {
    errorStatus = error.status.toString()
    errorMessage = error.statusText || (error.data as { message?: string })?.message || errorMessage
  } else if (error instanceof Error) {
    errorMessage = error.message
  }

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          py: 8,
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 6,
            textAlign: 'center',
            maxWidth: 500,
          }}
        >
          <ErrorIcon sx={{ fontSize: 80, color: 'error.main', mb: 2 }} />

          <Typography variant="h1" component="h1" sx={{ fontSize: '4rem', mb: 2 }}>
            {errorStatus}
          </Typography>

          <Typography variant="h5" component="h2" gutterBottom>
            Oops! Something went wrong
          </Typography>

          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            {errorMessage}
          </Typography>

          <Button component={Link} to="/" variant="contained" startIcon={<Home />} size="large">
            Back to Home
          </Button>
        </Paper>
      </Box>
    </Container>
  )
}

export default ErrorPage
