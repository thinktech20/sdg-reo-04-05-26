import { Box, Typography, Paper, Button, Grid } from '@mui/material'
import { Assessment, Search, List as ListIcon, ArrowForward } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'

/**
 * Home page / Dashboard
 * Landing page with quick-action cards for the Reliability Engineer workflow.
 */
const HomePage = () => {
  const navigate = useNavigate()

  const cards = [
    {
      icon: <ListIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />,
      title: 'Units',
      description:
        'Browse active units with planned outages. Expand any unit to view its components and launch a reliability assessment.',
      action: () => navigate('/units'),
      label: 'View Units',
      disabled: false,
    },
    {
      icon: <Search sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />,
      title: 'Search by ESN',
      description:
        'Know the Equipment Serial Number? Enter it in the Units search bar to retrieve unit details and start an assessment instantly.',
      action: () => navigate('/units'),
      label: 'Search Equipment',
      disabled: false,
    },
    {
      icon: <Assessment sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />,
      title: 'My Assessments',
      description: 'View and manage your in-progress risk assessments across all units.',
      action: () => {},
      label: 'Coming Soon',
      disabled: true,
    },
  ]

  return (
    <Box>
      <Typography variant="h4" component="h1" fontWeight={700} gutterBottom>
        Services Demand Generation
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph>
        AI-powered reliability assessment for gas turbine generator components.
      </Typography>

      <Grid container spacing={3} sx={{ mt: 3 }}>
        {cards.map((card) => (
          <Grid key={card.title} size={{ xs: 12, md: 4 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 3,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s, box-shadow 0.2s',
                ...(!card.disabled && {
                  cursor: 'pointer',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4,
                  },
                }),
              }}
              onClick={card.disabled ? undefined : () => { void card.action() }}
            >
              {card.icon}
              <Typography variant="h6" fontWeight={600} gutterBottom>
                {card.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3, flex: 1 }}>
                {card.description}
              </Typography>
              <Button
                variant={card.disabled ? 'outlined' : 'contained'}
                fullWidth
                disabled={card.disabled}
                endIcon={!card.disabled ? <ArrowForward /> : undefined}
                onClick={(e) => {
                  e.stopPropagation()
                  void card.action()
                }}
              >
                {card.label}
              </Button>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  )
}

export default HomePage
