# app/services/queue_service.py
import redis
from rq import Queue, Job, Worker
from typing import Optional, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing job queues with Redis and RQ"""
    
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            
            # Create different queues for different priorities
            self.default_queue = Queue('default', connection=self.redis_client)
            self.high_priority_queue = Queue('high', connection=self.redis_client)
            self.ml_queue = Queue('ml_processing', connection=self.redis_client)
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Set to None for graceful degradation
            self.redis_client = None
            self.default_queue = None
            self.high_priority_queue = None
            self.ml_queue = None
    
    async def enqueue_change_detection_job(
        self,
        job_id: str,
        priority: str = 'normal',
        timeout: int = 3600  # 1 hour timeout
    ) -> Optional[str]:
        """
        Enqueue a change detection job for processing
        
        Args:
            job_id: Database job ID
            priority: 'high' or 'normal'
            timeout: Job timeout in seconds
            
        Returns:
            Queue job ID or None if queueing fails
        """
        try:
            if not self.ml_queue:
                logger.warning("Redis queue not available, job will remain pending")
                return None
            
            # Choose queue based on priority
            queue = self.high_priority_queue if priority == 'high' else self.ml_queue
            
            # Enqueue the job
            job = queue.enqueue(
                'app.services.worker_tasks.process_change_detection_job',
                job_id,
                job_timeout=timeout,
                job_id=f"change_detection_{job_id}"
            )
            
            logger.info(f"Enqueued change detection job {job_id} with queue ID {job.id}")
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}")
            return None
    
    async def get_job_status(self, queue_job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a queued job"""
        try:
            if not self.redis_client:
                return None
                
            job = Job.fetch(queue_job_id, connection=self.redis_client)
            
            return {
                "id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at,
                "started_at": job.started_at,
                "ended_at": job.ended_at,
                "result": job.result,
                "exc_info": job.exc_info
            }
            
        except Exception as e:
            logger.error(f"Error getting job status {queue_job_id}: {e}")
            return None
    
    async def cancel_job(self, queue_job_id: str) -> bool:
        """Cancel a queued job"""
        try:
            if not self.redis_client:
                return False
                
            job = Job.fetch(queue_job_id, connection=self.redis_client)
            job.cancel()
            
            logger.info(f"Cancelled queue job {queue_job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling job {queue_job_id}: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about all queues"""
        try:
            if not self.redis_client:
                return {}
                
            stats = {}
            
            for queue_name, queue in [
                ('default', self.default_queue),
                ('high_priority', self.high_priority_queue),
                ('ml_processing', self.ml_queue)
            ]:
                if queue:
                    stats[queue_name] = {
                        'pending': len(queue),
                        'failed': len(queue.failed_job_registry),
                        'finished': len(queue.finished_job_registry),
                        'started': len(queue.started_job_registry)
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def clear_failed_jobs(self, queue_name: str = 'ml_processing') -> int:
        """Clear failed jobs from a queue (synchronous for admin tasks)"""
        try:
            if not self.redis_client:
                return 0
                
            queue = getattr(self, f'{queue_name}_queue', self.ml_queue)
            if not queue:
                return 0
                
            failed_count = len(queue.failed_job_registry)
            queue.failed_job_registry.clear()
            
            logger.info(f"Cleared {failed_count} failed jobs from {queue_name} queue")
            return failed_count
            
        except Exception as e:
            logger.error(f"Error clearing failed jobs: {e}")
            return 0
    
    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            if not self.redis_client:
                return False
            self.redis_client.ping()
            return True
        except Exception:
            return False