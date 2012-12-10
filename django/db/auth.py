import logging
from django.contrib.auth.models import User
from hmslincs.auth import authenticate

logger = logging.getLogger(__name__)

class CustomAuthenticationBackend():
    """
    For a user registered with our system, 
    - if superuser, find the user and check the password against the database user table entry,
    - if non-superuser, find the user then check the password against the Ecommons server;
    -- username will also be the ecommons_id
    """

    def authenticate(self, username=None, password=None):
        logger.info(str(('find and authenticate the user', username)))
        try:
            user = User.objects.get(username=username)
            if(username == 'admin'):
                logger.info(str(('authenticate admin superuser', user)))
                if(user.check_password(password)):
                    logger.info(str(('authenticated',user)))
                    return user
                else:
                    logger.info(str('incorrect password given for superuser:', user))
                    return None
            logger.info("found non-superuser user, now try to authenticate with ecommons...")
            if(authenticate(username, password)):
                logger.info(str(('user authenticated with the ecommons server', user)))
                if(user.is_active):
                    return user
                else:
                    logger.warn(str(('user authenticated, but is not active',user)))
            else:
                logger.warn(str(('user not authenticated with the ecommons server', user)))
        except User.DoesNotExist, e:
            logger.error(str(('no such user with the id', username)))
        except Exception, e:
            logger.error(str(('failed to authenticate', username, e)))

    def get_user(self, user_id):
        logger.info(str(('get_user',user_id)))
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None